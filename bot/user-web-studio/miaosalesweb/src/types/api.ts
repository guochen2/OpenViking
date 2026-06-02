/** 后台统一响应结构，status=1 表示成功 */
export interface ApiEnvelope<T = unknown> {
  status: number;
  message: string;
  results: T;
  timestamp: number;
}

export const API_STATUS_OK = 1;
