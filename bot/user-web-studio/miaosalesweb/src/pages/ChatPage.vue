<template>
  <q-layout view="hHh Lpr lFf" class="chat-layout">
    <q-header elevated class="bg-white text-dark">
      <q-toolbar>
        <q-toolbar-title class="text-weight-medium">Miao Sales 对话</q-toolbar-title>
        <q-chip dense outline color="primary" class="q-mr-sm">
          {{ authStore.username }}
        </q-chip>
        <q-btn flat dense icon="logout" label="退出" @click="onLogout" />
      </q-toolbar>
    </q-header>

    <q-drawer show-if-above bordered :width="280" class="session-drawer">
      <div class="q-pa-md">
        <q-btn
          color="primary"
          icon="add"
          label="新建会话"
          class="full-width"
          unelevated
          :loading="chatStore.creatingSession"
          :disable="chatStore.hasExecutingSession || chatStore.creatingSession"
          @click="onCreateSession"
        />
        <div v-if="chatStore.hasExecutingSession" class="text-caption text-orange q-mt-sm">
          当前有会话正在执行，请等待完成
        </div>
      </div>

      <q-separator />

      <q-list padding>
        <q-item
          v-for="session in chatStore.sessions"
          :key="session.id"
          clickable
          v-ripple
          :active="session.id === chatStore.activeSessionId"
          active-class="session-active"
          @click="chatStore.selectSession(session.id)"
        >
          <q-item-section>
            <q-item-label lines="1">{{ session.title }}</q-item-label>
            <q-item-label caption lines="1">
              {{ formatTime(session.updatedAt) }}
            </q-item-label>
          </q-item-section>
          <q-item-section side>
            <q-badge
              :color="session.status === 'executing' ? 'orange' : 'grey-5'"
              :label="session.status === 'executing' ? '执行中' : '已完成'"
            />
          </q-item-section>
        </q-item>
      </q-list>
    </q-drawer>

    <q-page-container>
      <q-page class="chat-page column">
        <div ref="messageContainer" class="messages-area col q-pa-md">
          <div v-if="chatStore.activeMessages.length === 0" class="empty-state">
            <q-icon name="chat_bubble_outline" size="48px" color="grey-5" />
            <div class="text-grey-6 q-mt-md">发送消息开始对话</div>
          </div>

          <div
            v-for="message in chatStore.activeMessages"
            :key="message.id"
            class="message-row"
            :class="message.role"
          >
            <div class="message-bubble">
              <div class="message-meta">
                {{ message.role === 'user' ? '我' : '助手' }}
                <span class="text-grey-6"> · {{ formatTime(message.timestamp) }}</span>
              </div>

              <div v-if="message.status === 'streaming'" class="q-mb-sm">
                <q-spinner-dots color="primary" size="24px" />
                <span class="text-caption text-grey-7 q-ml-sm">正在回复...</span>
              </div>

              <div v-if="message.events.length > 0" class="events-block q-mb-sm">
                <q-expansion-item
                  dense
                  expand-separator
                  icon="settings"
                  label="执行过程"
                  header-class="text-caption"
                >
                  <q-list dense bordered class="rounded-borders">
                    <q-item v-for="(evt, idx) in message.events" :key="idx">
                      <q-item-section>
                        <q-item-label caption> [{{ evt.phase }}] {{ evt.event }} </q-item-label>
                        <q-item-label v-if="evt.data" class="text-body2 event-data">
                          {{ formatEventData(evt.data) }}
                        </q-item-label>
                      </q-item-section>
                    </q-item>
                  </q-list>
                </q-expansion-item>
              </div>

              <div
                v-if="message.content"
                class="message-content"
                :class="{ 'text-negative': message.status === 'error' }"
              >
                <MarkdownContent
                  v-if="message.role === 'assistant' && message.status !== 'error'"
                  :content="message.content"
                />
                <span v-else>{{ message.content }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="input-area q-pa-md">
          <q-banner
            v-if="chatStore.isExecuting"
            dense
            rounded
            class="bg-orange-1 text-orange-10 q-mb-sm"
          >
            助手正在处理中，请等待结束后再发送新消息
          </q-banner>
          <div class="row q-gutter-sm items-end">
            <q-input
              v-model="inputText"
              type="textarea"
              autogrow
              outlined
              dense
              class="col"
              placeholder="输入消息..."
              :disable="chatStore.isExecuting"
              @keydown.enter.exact.prevent="onSend"
            />
            <q-btn
              color="primary"
              icon="send"
              label="发送"
              unelevated
              :loading="sending"
              :disable="!canSend"
              @click="onSend"
            />
          </div>
        </div>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useQuasar } from 'quasar';
import { useAuthStore } from 'stores/auth-store';
import { useChatStore } from 'stores/chat-store';
import MarkdownContent from 'components/MarkdownContent.vue';

const router = useRouter();
const $q = useQuasar();
const authStore = useAuthStore();
const chatStore = useChatStore();

const inputText = ref('');
const sending = ref(false);
const messageContainer = ref<HTMLElement | null>(null);

const canSend = computed(
  () =>
    inputText.value.trim().length > 0 &&
    !chatStore.isExecuting &&
    !sending.value &&
    !!chatStore.activeSessionId
);

void chatStore.initForUser().catch((error: unknown) => {
  $q.notify({
    type: 'negative',
    message: error instanceof Error ? error.message : '初始化会话失败',
  });
});

watch(
  () => chatStore.activeMessages.length,
  async () => {
    await nextTick();
    scrollToBottom();
  }
);

watch(
  () => chatStore.activeMessages.map((m) => m.content).join(''),
  async () => {
    await nextTick();
    scrollToBottom();
  }
);

function scrollToBottom() {
  const el = messageContainer.value;
  if (el) {
    el.scrollTop = el.scrollHeight;
  }
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function formatEventData(data: unknown): string {
  if (typeof data === 'string') return data;
  if (data === null || data === undefined) return '';
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    // eslint-disable-next-line @typescript-eslint/no-base-to-string
    return String(data);
  }
}

async function onCreateSession() {
  if (chatStore.hasExecutingSession) {
    $q.notify({
      type: 'warning',
      message: '请等待当前会话执行完成后再新建',
    });
    return;
  }
  try {
    const session = await chatStore.createSession();
    if (!session) {
      $q.notify({
        type: 'warning',
        message: '无法创建会话，请稍后重试',
      });
    }
  } catch (error) {
    $q.notify({
      type: 'negative',
      message: error instanceof Error ? error.message : '创建会话失败',
    });
  }
}

async function onSend() {
  if (!canSend.value) return;
  const text = inputText.value.trim();
  inputText.value = '';
  sending.value = true;
  try {
    await chatStore.sendMessage(text);
  } catch (error) {
    $q.notify({
      type: 'negative',
      message: error instanceof Error ? error.message : '发送失败',
    });
  } finally {
    sending.value = false;
  }
}

function onLogout() {
  authStore.logout();
  void router.push('/login');
}
</script>

<style scoped lang="scss">
.chat-layout {
  background: #f7f8fa;
}

.session-drawer {
  background: #fff;
}

.session-active {
  background: rgba(25, 118, 210, 0.08);
}

.chat-page {
  min-height: calc(100vh - 50px);
}

.messages-area {
  overflow-y: auto;
}

.empty-state {
  height: 100%;
  min-height: 240px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.message-row {
  display: flex;
  margin-bottom: 16px;

  &.user {
    justify-content: flex-end;

    .message-bubble {
      background: #e3f2fd;
      border-bottom-right-radius: 4px;
    }
  }

  &.assistant {
    justify-content: flex-start;

    .message-bubble {
      background: #fff;
      border-bottom-left-radius: 4px;
    }
  }
}

.message-bubble {
  max-width: min(720px, 85%);
  padding: 12px 16px;
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.message-meta {
  font-size: 12px;
  margin-bottom: 6px;
}

.message-content {
  word-break: break-word;
  line-height: 1.6;
}

.event-data {
  white-space: pre-wrap;
  font-family: monospace;
  font-size: 12px;
}

.input-area {
  background: #fff;
  border-top: 1px solid #e0e0e0;
}
</style>
