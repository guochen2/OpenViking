"""Pydantic models for HTTP Web channel (external web SSE API)."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ConversationPhase(str, Enum):
    """High-level conversation turn state for SSE clients."""

    STARTED = "started"
    PROCESSING = "processing"
    RESPONDING = "responding"
    COMPLETED = "completed"
    ERROR = "error"


class StreamEventType(str, Enum):
    """Granular agent event type within a conversation turn."""

    ITERATION = "iteration"
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RESPONSE = "response"
    NO_REPLY = "no_reply"


class HttpChatRequest(BaseModel):
    """Request body for the SSE chat endpoint."""

    message: str = Field(..., description="User message", min_length=1)
    user_id: str = Field(..., description="User identifier", min_length=1)
    session_id: str = Field(..., description="Session identifier", min_length=1)

class HttpChatStepRequest(BaseModel):
    """Execution step record model"""
    task_id: Optional[str] = Field(None, description="Unique task identifier")
    stage: str = Field(..., description="Current execution stage")
    status: str = Field("running", description="Status of the current step")
    message: str = Field("", description="Step description message")
    payload: Optional[Any] = Field(None, description="Additional business payload data")
    timestamp: str = Field(..., description="ISO formatted timestamp")
    session_id: str = Field(..., description="Unique session identifier")
    
    
class HttpStreamEvent(BaseModel):
    """Single SSE event describing conversation progress."""

    phase: ConversationPhase = Field(..., description="Conversation turn phase")
    event: StreamEventType = Field(..., description="Agent event type")
    data: Any = Field(default=None, description="Event payload")
    session_id: str = Field(..., description="Session identifier")
    user_id: str = Field(..., description="User identifier")
    timestamp: datetime = Field(default_factory=datetime.now, description="Event time")


class HttpStreamDone(BaseModel):
    """Terminal marker emitted before stream close."""

    phase: ConversationPhase = ConversationPhase.COMPLETED
    session_id: str
    user_id: str
    response_id: Optional[str] = None
    content: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)
