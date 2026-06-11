"""HTTP Web channel — SSE-only API for external web clients."""

import asyncio
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from vikingbot.bus.events import OutboundEventType, OutboundMessage
from vikingbot.bus.queue import MessageBus
from vikingbot.channels.base import BaseChannel
from bot.vikingbot.utils.trace import TRACE_HEADER, get_trace_id, set_trace_id
from vikingbot.channels.http_web_models import (
    ConversationPhase,
    HttpChatRequest,
    HttpChatStepRequest,
    HttpStreamDone,
    HttpStreamEvent,
    StreamEventType,
)
from vikingbot.config.schema import BaseChannelConfig, ChannelType, Config, SessionKey


class HttpWebPending:
    """Tracks a pending SSE response for one chat turn."""

    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        self.final_content: Optional[str] = None
        self.response_id: Optional[str] = None
        self.stream_queue: asyncio.Queue[Optional[HttpStreamEvent | HttpStreamDone]] = (
            asyncio.Queue()
        )

    async def emit(
        self,
        phase: ConversationPhase,
        event: StreamEventType,
        data: Any = None,
    ) -> None:
        await self.stream_queue.put(
            HttpStreamEvent(
                phase=phase,
                event=event,
                data=data,
                session_id=self.session_id,
                user_id=self.user_id,
            )
        )

    async def complete(self, content: str, response_id: str | None) -> None:
        self.final_content = content
        self.response_id = response_id
        await self.stream_queue.put(
            HttpStreamDone(
                session_id=self.session_id,
                user_id=self.user_id,
                response_id=response_id,
                content=content,
            )
        )

    async def error(self, message: str) -> None:
        await self.emit(ConversationPhase.ERROR, StreamEventType.RESPONSE, {"error": message})

    async def close(self) -> None:
        await self.stream_queue.put(None)


class HttpWebChannelConfig(BaseChannelConfig):
    """Configuration for HTTP Web SSE channel."""

    type: ChannelType = ChannelType.WEB_HTTP
    enabled: bool = True
    auth_key: str = ""
    allow_from: list[str] = []
    max_concurrent_requests: int = 100
    id: str = "default"

    def channel_id(self) -> str:
        return self.id

async def get_trace_id_header(raw_req: Request) -> Optional[str]:
    trace_id = raw_req.headers.get(TRACE_HEADER) or raw_req.headers.get("Trace-Id")
    # 自动设置到异步上下文
    if trace_id:
        set_trace_id(trace_id)
    return trace_id
class HttpWebChannel(BaseChannel):
    """SSE-only HTTP channel for external web applications."""

    name: str = "http_web"

    def __init__(
        self,
        config: HttpWebChannelConfig,
        bus: MessageBus,
        workspace_path: Path | None = None,
        app: FastAPI | None = None,
        global_config: Config | None = None,
    ):
        super().__init__(config, bus, workspace_path)
        self.config = config
        self._global_config = global_config
        self._pending: Dict[str, HttpWebPending] = {}
        self._router: Optional[APIRouter] = None
        self._app = app

    async def start(self) -> None:
        self._running = True
        if self._app is not None:
            self._setup_routes()
        logger.info("HTTP Web channel started")

    async def stop(self) -> None:
        self._running = False
        for pending in self._pending.values():
            await pending.close()
        self._pending.clear()
        logger.info("HTTP Web channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        if msg.session_key.type != ChannelType.WEB_HTTP.value:
            return

        session_id = msg.session_key.chat_id
        pending = self._pending.get(session_id)
        if not pending:
            return

        event_map = {
            OutboundEventType.ITERATION: (ConversationPhase.PROCESSING, StreamEventType.ITERATION),
            OutboundEventType.REASONING: (ConversationPhase.PROCESSING, StreamEventType.REASONING),
            OutboundEventType.TOOL_CALL: (ConversationPhase.PROCESSING, StreamEventType.TOOL_CALL),
            OutboundEventType.TOOL_RESULT: (
                ConversationPhase.PROCESSING,
                StreamEventType.TOOL_RESULT,
            ),
        }

        if msg.event_type in event_map:
            phase, event = event_map[msg.event_type]
            await pending.emit(phase, event, msg.content)
            return

        if msg.event_type in (OutboundEventType.RESPONSE, OutboundEventType.NO_REPLY):
            content = msg.content or ""
            response_id = msg.response_id
            await pending.emit(
                ConversationPhase.RESPONDING,
                StreamEventType.RESPONSE if msg.event_type == OutboundEventType.RESPONSE else StreamEventType.NO_REPLY,
                {"content": content, "response_id": response_id},
            )
            await pending.complete(content, response_id)
            await pending.close()

    def get_router(self) -> APIRouter:
        if self._router is None:
            self._router = self._create_router()
        return self._router

    def _setup_routes(self) -> None:
        if self._app is None:
            return
        router = self.get_router()
        self._app.include_router(router, prefix="/web/v1")
        logger.info("HTTP Web SSE routes registered at /web/v1")

    def _create_router(self) -> APIRouter:
        router = APIRouter()
        channel = self

        async def verify_auth_key(
            auth_key: Optional[str] = Header(None, alias="auth-key"),
        ) -> bool:
            expected = channel.config.auth_key
            if not expected:
                raise HTTPException(
                    status_code=503,
                    detail="HTTP Web channel auth_key is not configured",
                )
            if not auth_key:
                raise HTTPException(status_code=401, detail="auth-key header required")
            if not secrets.compare_digest(auth_key, expected):
                raise HTTPException(status_code=403, detail="Invalid auth-key")
            return True

        @router.post("/chat/stream")
        async def chat_stream(
            request: HttpChatRequest,
            authorized: bool = Depends(verify_auth_key),
            _: None = Depends(get_trace_id_header)
        ):
            return await channel._handle_chat_stream(request)
        
        @router.post("/chat/step")
        async def chat_step(request: HttpChatStepRequest,_: None = Depends(get_trace_id_header)):
            # 1. 校验会话ID
            session_id = request.session_id
            if not session_id:
                return

            # 2. 获取会话实例，不存在则直接返回
            pending = self._pending.get(session_id)
            if not pending:
                return

            # 3. 状态 -> 阶段+事件 映射（仿照原 event_map 写法）
            status_event_map = {
                "running": (ConversationPhase.PROCESSING, StreamEventType.TOOL_RESULT),
                "success": (ConversationPhase.RESPONDING, StreamEventType.TOOL_RESULT),
                "failed": (ConversationPhase.ERROR, StreamEventType.TOOL_RESULT),
            }

            # 4. 匹配状态并推送事件
            if request.status in status_event_map:
                phase, event = status_event_map[request.status]
                # 组装推送内容，按需拼接 message / payload / task_id 等
                content = {
                    "task_id": request.task_id,
                    "stage": request.stage,
                    "message": request.message,
                    "payload": request.payload,
                    "timestamp": request.timestamp
                }
                await pending.emit(phase, event, content)
            return
        return router

    async def _handle_chat_stream(self, request: HttpChatRequest) -> StreamingResponse:
        session_id = request.session_id
        user_id = request.user_id

        if not self.is_allowed(user_id):
            raise HTTPException(status_code=403, detail="User not allowed")

        if session_id in self._pending:
            raise HTTPException(
                status_code=409,
                detail="Session has an active request; wait for completion",
            )

        pending = HttpWebPending(session_id=session_id, user_id=user_id)
        self._pending[session_id] = pending

        async def event_generator():
            try:
                await pending.emit(ConversationPhase.STARTED, StreamEventType.ITERATION, None)

                session_key = SessionKey(
                    type=ChannelType.WEB_HTTP.value,
                    channel_id=self.config.channel_id(),
                    chat_id=session_id,
                )
                from vikingbot.bus.events import InboundMessage

                msg = InboundMessage(
                    session_key=session_key,
                    sender_id=get_trace_id(),
                    content=request.message
                )
                await self.bus.publish_inbound(msg)

                while True:
                    try:
                        item = await asyncio.wait_for(pending.stream_queue.get(), timeout=300.0)
                    except asyncio.TimeoutError:
                        await pending.error("Request timeout")
                        yield f"data: {HttpStreamEvent(phase=ConversationPhase.ERROR, event=StreamEventType.RESPONSE, data={'error': 'timeout'}, session_id=session_id, user_id=user_id).model_dump_json()}\n\n"
                        break

                    if item is None:
                        break

                    yield f"data: {item.model_dump_json()}\n\n"

            except Exception as e:
                logger.exception(f"HTTP Web stream error: {e}")
                error_event = HttpStreamEvent(
                    phase=ConversationPhase.ERROR,
                    event=StreamEventType.RESPONSE,
                    data={"error": str(e)},
                    session_id=session_id,
                    user_id=user_id,
                )
                yield f"data: {error_event.model_dump_json()}\n\n"
            finally:
                self._pending.pop(session_id, None)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
