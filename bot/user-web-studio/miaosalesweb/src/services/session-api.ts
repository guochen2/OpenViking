import { assertApiSuccess, sessionHttp } from 'src/services/http';
import type { ApiEnvelope } from 'src/types/api';

/**
 * 从后台创建会话并返回 sessionId。
 * GET /api/test/session?userid={userId}
 */
export async function fetchSessionId(userId: string): Promise<string> {
  const { data } = await sessionHttp.get<ApiEnvelope<string>>('/api/test/session', {
    params: { userid: userId },
  });

  const sessionId = assertApiSuccess(data);
  const normalized = String(sessionId ?? '').trim();
  if (!normalized) {
    throw new Error('会话 ID 无效');
  }
  return normalized;
}
