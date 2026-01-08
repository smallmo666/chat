import asyncio
from contextvars import ContextVar
from typing import Any, Optional

# ContextVar to store the current request's SSE queue
_request_queue: ContextVar[Optional[asyncio.Queue]] = ContextVar("request_queue", default=None)

class EventBus:
    """
    全局事件总线，用于在任何深层代码中向当前请求的 SSE 流推送事件。
    使用 ContextVars 隔离不同请求的上下文。
    """
    
    @staticmethod
    def set_queue(queue: asyncio.Queue):
        """在请求开始时设置当前的 SSE queue"""
        _request_queue.set(queue)

    @staticmethod
    def get_queue() -> Optional[asyncio.Queue]:
        return _request_queue.get()

    @staticmethod
    async def emit(event_type: str, content: Any = "", **kwargs):
        """
        发送 SSE 事件。
        
        Args:
            event_type: 事件类型 (e.g., "substep", "thinking", "clarification")
            content: 事件主要内容
            **kwargs: 其他附加字段 (e.g., node, step, detail)
        """
        queue = _request_queue.get()
        if queue:
            payload = {"type": event_type, "content": content}
            payload.update(kwargs)
            await queue.put(payload)

    @staticmethod
    async def emit_substep(node: str, step: str, detail: str, metrics: dict = None):
        """专门发送 substep 事件的快捷方法"""
        import time
        await EventBus.emit(
            "substep", 
            node=node,
            step=step,
            detail=detail,
            metrics=metrics,
            ts=int(time.time() * 1000)
        )
