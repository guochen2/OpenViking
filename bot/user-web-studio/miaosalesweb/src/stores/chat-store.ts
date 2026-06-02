import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { streamChat } from 'src/services/chat-api';
import { fetchSessionId } from 'src/services/session-api';
import type {
  ChatMessage,
  ChatSession,
  HttpStreamDonePayload,
  HttpStreamEventPayload,
  SessionStatus,
  StreamEventItem,
} from 'src/types/chat';
import { useAuthStore } from './auth-store';

const SESSIONS_KEY = 'miaosales_sessions';
const MESSAGES_KEY = 'miaosales_messages';

function createId(): string {
  return crypto.randomUUID();
}

function loadJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function saveJson(key: string, value: unknown) {
  localStorage.setItem(key, JSON.stringify(value));
}

export const useChatStore = defineStore('chat', () => {
  const authStore = useAuthStore();

  const sessionsByUser = ref<Record<string, ChatSession[]>>(loadJson(SESSIONS_KEY, {}));
  const messagesBySession = ref<Record<string, ChatMessage[]>>(loadJson(MESSAGES_KEY, {}));
  const activeSessionId = ref<string>('');
  const abortController = ref<AbortController | null>(null);
  const creatingSession = ref(false);

  const sessions = computed(() => sessionsByUser.value[authStore.userId] ?? []);

  const activeSession = computed(() =>
    sessions.value.find((session) => session.id === activeSessionId.value),
  );

  const activeMessages = computed(
    () => messagesBySession.value[activeSessionId.value] ?? [],
  );

  const isExecuting = computed(() => activeSession.value?.status === 'executing');

  const hasExecutingSession = computed(() =>
    sessions.value.some((session) => session.status === 'executing'),
  );

  function persistSessions() {
    saveJson(SESSIONS_KEY, sessionsByUser.value);
  }

  function persistMessages() {
    saveJson(MESSAGES_KEY, messagesBySession.value);
  }

  function ensureUserSessions(): ChatSession[] {
    if (!sessionsByUser.value[authStore.userId]) {
      sessionsByUser.value[authStore.userId] = [];
    }
    return sessionsByUser.value[authStore.userId] as ChatSession[];
  }

  function updateSessionStatus(sessionId: string, status: SessionStatus) {
    const list = ensureUserSessions();
    const session = list.find((item) => item.id === sessionId);
    if (!session) return;
    session.status = status;
    session.updatedAt = new Date().toISOString();
    persistSessions();
  }

  async function createSession(): Promise<ChatSession | null> {
    if (hasExecutingSession.value || creatingSession.value) return null;

    creatingSession.value = true;
    try {
      const sessionId = await fetchSessionId(authStore.userId);
      const now = new Date().toISOString();
      const session: ChatSession = {
        id: sessionId,
        title: '新会话',
        createdAt: now,
        updatedAt: now,
        status: 'completed',
      };

      ensureUserSessions().unshift(session);
      messagesBySession.value[session.id] = [];
      activeSessionId.value = session.id;
      persistSessions();
      persistMessages();
      return session;
    } finally {
      creatingSession.value = false;
    }
  }

  function selectSession(sessionId: string) {
    activeSessionId.value = sessionId;
  }

  function appendMessage(sessionId: string, message: ChatMessage) {
    if (!messagesBySession.value[sessionId]) {
      messagesBySession.value[sessionId] = [];
    }
    messagesBySession.value[sessionId].push(message);
    persistMessages();
  }

  function updateAssistantMessage(
    sessionId: string,
    messageId: string,
    patch: Partial<ChatMessage>,
  ) {
    const messages = messagesBySession.value[sessionId];
    if (!messages) return;
    const index = messages.findIndex((item) => item.id === messageId);
    if (index < 0) return;
    messages[index] = { ...messages[index], ...patch } as ChatMessage;
    persistMessages();
  }

  function updateSessionTitle(sessionId: string, title: string) {
    const list = ensureUserSessions();
    const session = list.find((item) => item.id === sessionId);
    if (!session) return;
    session.title = title.slice(0, 30) || '新会话';
    session.updatedAt = new Date().toISOString();
    persistSessions();
  }

  async function sendMessage(content: string): Promise<boolean> {
    const trimmed = content.trim();
    if (!trimmed || !activeSessionId.value || isExecuting.value) return false;

    const sessionId = activeSessionId.value;
    const userMessage: ChatMessage = {
      id: createId(),
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
      status: 'done',
      events: [],
    };

    const assistantMessage: ChatMessage = {
      id: createId(),
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      status: 'streaming',
      events: [],
    };

    appendMessage(sessionId, userMessage);
    appendMessage(sessionId, assistantMessage);
    updateSessionStatus(sessionId, 'executing');

    const session = activeSession.value;
    if (session?.title === '新会话') {
      updateSessionTitle(sessionId, trimmed);
    }

    const controller = new AbortController();
    abortController.value = controller;

    const handleEvent = (event: HttpStreamEventPayload) => {
      const streamEvent: StreamEventItem = {
        phase: event.phase,
        event: event.event,
        data: event.data,
        timestamp: event.timestamp,
      };

      const messages = messagesBySession.value[sessionId] ?? [];
      const assistant = messages.find((item) => item.id === assistantMessage.id);
      if (!assistant) return;

      assistant.events = [...assistant.events, streamEvent];

      if (event.event === 'response' && event.data && typeof event.data === 'object') {
        const data = event.data as { content?: string };
        if (typeof data.content === 'string') {
          assistant.content = data.content;
        }
      }

      if (event.phase === 'error') {
        assistant.status = 'error';
        if (!assistant.content) {
          const data = event.data as { error?: string } | null;
          assistant.content = data?.error ?? '请求失败';
        }
      }

      updateAssistantMessage(sessionId, assistantMessage.id, {
        content: assistant.content,
        status: assistant.status,
        events: assistant.events,
      });
    };

    const handleDone = (done: HttpStreamDonePayload) => {
      updateAssistantMessage(sessionId, assistantMessage.id, {
        content: done.content || '',
        status: 'done',
      });
      updateSessionStatus(sessionId, 'completed');
    };

    try {
      await streamChat({
        message: trimmed,
        userId: authStore.userId,
        sessionId,
        signal: controller.signal,
        onEvent: handleEvent,
        onDone: handleDone,
        onError: () => undefined,
      });
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : '请求失败';
      updateAssistantMessage(sessionId, assistantMessage.id, {
        content: message,
        status: 'error',
      });
      updateSessionStatus(sessionId, 'completed');
      throw error;
    } finally {
      abortController.value = null;
      if (sessionsByUser.value[authStore.userId]?.find((s) => s.id === sessionId)?.status === 'executing') {
        updateSessionStatus(sessionId, 'completed');
      }
    }
  }

  async function initForUser(): Promise<void> {
    const list = ensureUserSessions();
    if (list.length === 0) {
      await createSession();
      return;
    }
    if (!activeSessionId.value || !list.some((item) => item.id === activeSessionId.value)) {
      activeSessionId.value = list[0]?.id ?? '';
    }
  }

  return {
    sessions,
    activeSessionId,
    activeSession,
    activeMessages,
    isExecuting,
    hasExecutingSession,
    creatingSession,
    createSession,
    selectSession,
    sendMessage,
    initForUser,
  };
});
