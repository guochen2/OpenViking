import type { HttpStreamDonePayload, HttpStreamEventPayload } from 'src/types/chat';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';
const AUTH_KEY = import.meta.env.VITE_AUTH_KEY ?? 'dev-auth-key';

export interface StreamChatOptions {
  message: string;
  userId: string;
  sessionId: string;
  signal?: AbortSignal;
  onEvent: (event: HttpStreamEventPayload) => void;
  onDone: (done: HttpStreamDonePayload) => void;
  onError: (error: Error) => void;
}

function parseSseBlock(block: string): HttpStreamEventPayload | HttpStreamDonePayload | null {
  const dataLine = block
    .split('\n')
    .map((line) => line.trim())
    .find((line) => line.startsWith('data:'));
  if (!dataLine) return null;

  const json = dataLine.slice(5).trim();
  if (!json) return null;

  try {
    return JSON.parse(json) as HttpStreamEventPayload | HttpStreamDonePayload;
  } catch {
    return null;
  }
}

function isDonePayload(
  payload: HttpStreamEventPayload | HttpStreamDonePayload,
): payload is HttpStreamDonePayload {
  return payload.phase === 'completed' && 'content' in payload && !('event' in payload);
}

export async function streamChat(options: StreamChatOptions): Promise<void> {
  const url = `${API_BASE}/web/v1/chat/stream`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'auth-key': AUTH_KEY,
    },
    body: JSON.stringify({
      message: options.message,
      user_id: options.userId,
      session_id: options.sessionId,
    }),
    signal: options.signal,
  } as any);

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // ignore parse errors
    }
    throw new Error(detail || `HTTP ${response.status}`);
  }

  if (!response.body) {
    throw new Error('Empty response body');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() ?? '';

    for (const block of blocks) {
      const payload = parseSseBlock(block);
      if (!payload) continue;

      if (isDonePayload(payload)) {
        options.onDone(payload);
      } else {
        options.onEvent(payload);
      }
    }
  }
}
