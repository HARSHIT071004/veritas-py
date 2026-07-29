import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings
from app.data.cache import RedisCache

logger = logging.getLogger("clearlens.ratelimit")

WINDOW = 3600


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_cache=None):
        super().__init__(app)
        self._redis = redis_cache

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/api/v1/health", "/", "/api/status", "/api/status"):
            return await call_next(request)

        if not self._redis or not self._redis._enabled:
            return await call_next(request)

        key = request.headers.get("x-user-id", "") or request.client.host if request.client else "unknown"
        max_req = settings.rate_limit_per_hour

        allowed, current = await self._check(key, max_req)
        if not allowed:
            from starlette.responses import JSONResponse
            logger.warning("Rate limit exceeded", extra={"key": key, "count": current, "limit": max_req})
            return JSONResponse(status_code=429, content={"success": False, "error": f"Rate limit exceeded. Max {max_req}/hour."})

        return await call_next(request)

    async def _check(self, key: str, max_requests: int) -> tuple[bool, int]:
        now = int(time.time())
        window_start = now - WINDOW
        try:
            async with self._redis._client.pipeline() as pipe:
                pipe.zremrangebyscore(f"rl:{key}", 0, window_start)
                pipe.zcard(f"rl:{key}")
                results = await pipe.execute()
            count = results[1] if isinstance(results, list) and len(results) > 1 else 0
            if count >= max_requests:
                return False, count
            await self._redis._client.zadd(f"rl:{key}", {str(now): now})
            await self._redis._client.expire(f"rl:{key}", WINDOW)
            return True, count + 1
        except Exception as e:
            logger.warning(f"Rate limit check failed, allowing: {e}")
            return True, 0
