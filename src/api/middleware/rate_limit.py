import time
from collections import deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse
from src.core.config import settings

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.window = settings.RATE_LIMIT_WINDOW
        self.max_req = settings.RATE_LIMIT_MAX_REQUESTS
        self.enabled = settings.ENABLE_RATE_LIMIT
        self.store = {}
    async def dispatch(self, request, call_next):
        if not self.enabled:
            return await call_next(request)
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        dq = self.store.get(ip)
        if dq is None:
            dq = deque()
            self.store[ip] = dq
        while dq and now - dq[0] > self.window:
            dq.popleft()
        if len(dq) >= self.max_req:
            return PlainTextResponse("rate limit exceeded", status_code=429)
        dq.append(now)
        return await call_next(request)
