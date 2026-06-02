import type { AxiosResponse } from 'axios';
import { chatAuthKey, chatHttp } from 'src/services/http';
import type { HttpStreamDonePayload, HttpStreamEventPayload } from 'src/types/chat';

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

async function readSseStream(
  stream: ReadableStream<Uint8Array>,
  options: StreamChatOptions,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
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
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      return;
    }
    const err = error instanceof Error ? error : new Error('SSE 读取失败');
    options.onError(err);
    throw err;
  }
}

function getReadableStreamFromAxiosResponse(response: AxiosResponse): ReadableStream<Uint8Array> {
  const body = response.data;
  if (body instanceof ReadableStream) {
    return body;
  }
  if (body && typeof body === 'object' && 'getReader' in body) {
    return body as ReadableStream<Uint8Array>;
  }
  throw new Error('SSE 流不可用');
}

/** 通过 axios（fetch 适配器）发起 SSE 对话请求 */
export async function streamChat(options: StreamChatOptions): Promise<void> {
  try {
    const response = await chatHttp.post(
      '/web/v1/chat/stream',
      {
        message: options.message,
        user_id: options.userId,
        session_id: options.sessionId,
      },
      {
        headers: {
          Accept: 'text/event-stream',
          'auth-key': chatAuthKey,
        },
        responseType: 'stream',
        adapter: 'fetch',
        signal: options.signal,
      } as any,
    );

    const stream = getReadableStreamFromAxiosResponse(response);
    await readSseStream(stream, options);
  } catch (error) {
    const err = error instanceof Error ? error : new Error('对话请求失败');
    options.onError(err);
    throw err;
  }
}
