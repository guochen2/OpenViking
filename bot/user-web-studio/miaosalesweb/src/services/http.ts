import axios, { type AxiosInstance, type AxiosResponse } from 'axios';
import { API_STATUS_OK, type ApiEnvelope } from 'src/types/api';

/** 会话服务（新建 sessionId） */
export const sessionApiBaseUrl = import.meta.env.VITE_SESSION_API_BASE_URL ?? '';

/** Bot 对话 SSE 服务 */
export const chatApiBaseUrl = import.meta.env.VITE_CHAT_API_BASE_URL ?? '';

export const chatAuthKey = import.meta.env.VITE_AUTH_KEY ?? 'dev-auth-key';

export function assertApiSuccess<T>(envelope: ApiEnvelope<T>): T {
  if (envelope.status !== API_STATUS_OK) {
    throw new Error(envelope.message || '请求失败');
  }
  return envelope.results;
}

function createHttpClient(baseURL: string): AxiosInstance {
  const instance = axios.create({
    baseURL,
    timeout: 60_000,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  instance.interceptors.response.use(
    (response: AxiosResponse<ApiEnvelope>) => response,
    (error: unknown) => {
      if (axios.isAxiosError(error)) {
        const data = error.response?.data as ApiEnvelope | undefined;
        if (data && typeof data === 'object' && 'message' in data) {
          return Promise.reject(new Error(data.message || error.message));
        }
        return Promise.reject(new Error(error.message || '网络请求失败'));
      }
      return Promise.reject(error instanceof Error ? error : new Error('网络请求失败'));
    },
  );

  return instance;
}

/** 会话管理 API（开发环境可走 devServer 代理 /api） */
export const sessionHttp = createHttpClient(sessionApiBaseUrl);

/** Bot 对话 API（开发环境可走 devServer 代理 /web） */
export const chatHttp = createHttpClient(chatApiBaseUrl);
