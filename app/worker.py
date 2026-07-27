import logging
from app.config import settings
from app.data.database import Database
from app.data.cache import RedisCache
from app.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger("clearlens.worker")


async def run_analysis_job(ctx, video_id: str, metadata: dict, user_id: str):
    redis_cache = RedisCache()
    job_id = f"job:{video_id}:{user_id[:8]}"

    try:
        await redis_cache.set(f"job:{job_id}", {"status": "processing", "video_id": video_id})
        orchestrator = PipelineOrchestrator()
        result = await orchestrator.run(video_id, metadata)

        if result.result:
            await redis_cache.set(f"job:{job_id}", {"status": "completed", "video_id": video_id, "result": result.result})
        else:
            await redis_cache.set(f"job:{job_id}", {"status": "failed", "video_id": video_id, "error": result.errors})
    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        await redis_cache.set(f"job:{job_id}", {"status": "failed", "video_id": video_id, "error": str(e)})
