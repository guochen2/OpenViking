from contextvars import ContextVar, Token
import uuid


TRACE_HEADER = "X-Trace-Id"

_trace_ctx: ContextVar[str] = ContextVar("trace_id", default="")


def new_trace_id() -> str:
    return uuid.uuid4().hex


def get_trace_id() -> str:
    return _trace_ctx.get()


def set_trace_id(trace_id: str) -> Token[str]:
    return _trace_ctx.set(trace_id)


def reset_trace_id(token: Token[str]) -> None:
    _trace_ctx.reset(token)


def resolve_trace_id(*candidates: str | None) -> str:
    """按优先级解析 traceId：显式参数 > 请求头/上下文 > 新生成。"""
    for value in candidates:
        if value and value.strip():
            return value.strip()
    current = get_trace_id()
    if current:
        return current
    return new_trace_id()