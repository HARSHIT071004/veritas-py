import time
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("clearlens.pipeline.stage")


@dataclass
class StageContext:
    video_id: str
    metadata: dict = field(default_factory=dict)
    mode: str = "balanced"
    user_id: str = ""
    prefetched: bool = False
    cache: Optional[Any] = None
    rag_engine: Optional[Any] = None
    db: Optional[Any] = None


@dataclass
class StageResult:
    success: bool = True
    data: dict = field(default_factory=dict)
    error: Optional[str] = None
    timing_ms: int = 0
    cached: bool = False


class PipelineStage(ABC):
    name: str = ""
    dependencies: list[str] = []

    def __init__(self):
        self._retries = 2
        self._retry_delay = 1.0

    @abstractmethod
    async def execute(self, ctx: StageContext, inputs: dict) -> StageResult:
        ...

    async def run(self, ctx: StageContext, inputs: dict) -> StageResult:
        cached = None
        if ctx.cache:
            cached = await ctx.cache.get(self.name, ctx.video_id, ctx.mode)
        if cached:
            logger.info(f"[{self.name}] Cache hit for {ctx.video_id}")
            return StageResult(data=cached, cached=True)

        for attempt in range(self._retries + 1):
            t0 = time.time()
            try:
                result = await self.execute(ctx, inputs)
                result.timing_ms = int((time.time() - t0) * 1000)
                if result.success and ctx.cache:
                    await ctx.cache.set(self.name, result.data, ctx.video_id, ctx.mode)
                return result
            except Exception as e:
                elapsed = int((time.time() - t0) * 1000)
                if attempt < self._retries:
                    wait = self._retry_delay * (attempt + 1)
                    logger.warning(f"[{self.name}] Attempt {attempt + 1} failed ({elapsed}ms): {e}, retrying in {wait}s")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"[{self.name}] All {self._retries + 1} attempts failed: {e}")
                    return StageResult(success=False, data={}, error=str(e), timing_ms=elapsed)
