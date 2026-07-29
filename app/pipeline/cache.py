import time
import json
import logging
import hashlib
from typing import Optional, Any
from app.config import settings

logger = logging.getLogger("clearlens.pipeline.cache")

L1_CACHE: dict[str, tuple[Any, float]] = {}
_L1_MAX = 512
_L1_TTL = 300

L2_REDIS = None
L3_SQLITE = None


class MultiLevelCache:
    def __init__(self, redis=None, db=None):
        global L2_REDIS, L3_SQLITE
        L2_REDIS = redis
        L3_SQLITE = db

    def _key(self, stage: str, *args, **kwargs) -> str:
        raw = f"{stage}:{json.dumps(args)}:{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.md5(raw.encode()).hexdigest()

    async def get(self, stage: str, *args, **kwargs) -> Optional[Any]:
        key = self._key(stage, *args, **kwargs)

        val = await self._l1_get(key)
        if val is not None:
            return val

        val = await self._l2_get(key)
        if val is not None:
            self._l1_set(key, val)
            return val

        val = await self._l3_get(key)
        if val is not None:
            self._l1_set(key, val)
            return val

        return None

    async def set(self, stage: str, value: Any, *args, ttl: int = None, **kwargs):
        key = self._key(stage, *args, **kwargs)
        ttl = ttl or settings.cache_ttl_seconds
        self._l1_set(key, value)
        await self._l2_set(key, value, ttl)
        await self._l3_set(key, value, ttl)

    async def delete(self, stage: str, *args, **kwargs):
        key = self._key(stage, *args, **kwargs)
        L1_CACHE.pop(key, None)
        await self._l2_delete(key)
        await self._l3_delete(key)

    async def clear(self):
        L1_CACHE.clear()
        await self._l2_clear()
        await self._l3_clear()

    def _l1_get(self, key: str) -> Optional[Any]:
        if key in L1_CACHE:
            val, ts = L1_CACHE[key]
            if time.time() - ts < _L1_TTL:
                return val
            del L1_CACHE[key]
        return None

    def _l1_set(self, key: str, value: Any):
        if len(L1_CACHE) >= _L1_MAX:
            oldest = min(L1_CACHE.keys(), key=lambda k: L1_CACHE[k][1])
            del L1_CACHE[oldest]
        L1_CACHE[key] = (value, time.time())

    async def _l2_get(self, key: str) -> Optional[Any]:
        if L2_REDIS is None:
            return None
        try:
            import redis.asyncio as aioredis
            val = await L2_REDIS.get(f"pipe:{key}")
            return json.loads(val) if val else None
        except Exception:
            return None

    async def _l2_set(self, key: str, value: Any, ttl: int):
        if L2_REDIS is None:
            return
        try:
            await L2_REDIS.setex(f"pipe:{key}", ttl, json.dumps(value, default=str))
        except Exception:
            pass

    async def _l2_delete(self, key: str):
        if L2_REDIS is None:
            return
        try:
            await L2_REDIS.delete(f"pipe:{key}")
        except Exception:
            pass

    async def _l2_clear(self):
        if L2_REDIS is None:
            return
        try:
            await L2_REDIS.flushdb()
        except Exception:
            pass

    async def _l3_get(self, key: str) -> Optional[Any]:
        if L3_SQLITE is None:
            return None
        try:
            from app.data.database import Database
            return L3_SQLITE.get_cached(key)
        except Exception:
            return None

    async def _l3_set(self, key: str, value: Any, ttl: int):
        if L3_SQLITE is None:
            return
        try:
            if isinstance(value, dict):
                L3_SQLITE.set_cache(key, value, ttl)
        except Exception:
            pass

    async def _l3_delete(self, key: str):
        pass

    async def _l3_clear(self):
        pass
