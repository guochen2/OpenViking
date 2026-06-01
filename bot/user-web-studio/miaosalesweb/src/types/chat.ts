export type SessionStatus = 'executing' | 'completed';

export type ConversationPhase =
  | 'started'
  | 'processing'
  | 'responding'
  | 'completed'
  | 'error';

export type StreamEventType =
  | 'iteration'
  | 'reasoning'
  | 'tool_call'
  | 'tool_result'
  | 'response'
  | 'no_reply';

export interface ChatSession {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  status: SessionStatus;
}

export interface StreamEventItem {
  phase: ConversationPhase;
  event: StreamEventType;
  data: unknown;
  timestamp: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  status: 'pending' | 'streaming' | 'done' | 'error';
  events: StreamEventItem[];
}

export interface HttpStreamDonePayload {
  phase: 'completed';
  session_id: string;
  user_id: string;
  response_id?: string;
  content: string;
  timestamp: string;
}

export interface HttpStreamEventPayload {
  phase: ConversationPhase;
  event: StreamEventType;
  data: unknown;
  session_id: string;
  user_id: string;
  timestamp: string;
}
