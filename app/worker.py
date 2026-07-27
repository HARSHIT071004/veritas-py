import logging
import uuid
from datetime import datetime, timezone
from app.config import settings
from app.data.cache import RedisCache
from app.pipeline.orchestrator import PipelineOrchestrator
from app.schemas.job import Job, JobStatus

logger = logging.getLogger("clearlens.worker")

REDIS_CACHE = None


async def get_redis():
    global REDIS_CACHE
    if REDIS_CACHE is None:
        REDIS_CACHE = RedisCache()
    return REDIS_CACHE


async def create_job(video_id: str, user_id: str, redis_cache: RedisCache) -> str:
    job_id = uuid.uuid4().hex[:12]
    job = Job(job_id=job_id, video_id=video_id, user_id=user_id, status=JobStatus.queued, created_at=datetime.now(timezone.utc).isoformat())
    await redis_cache.set(f"job:{job_id}", job.model_dump(), ttl=3600)
    return job_id


async def get_job(job_id: str, redis_cache: RedisCache) -> Job:
    data = await redis_cache.get(f"job:{job_id}")
    return Job(**data) if data else Job(job_id=job_id, video_id="", user_id="", status=JobStatus.failed, error="Job not found")


async def update_job(job_id: str, redis_cache: RedisCache, status: JobStatus, result: dict = None, error: str = None, progress: str = ""):
    data = await redis_cache.get(f"job:{job_id}")
    if data:
        data["status"] = status.value
        if result:
            data["result"] = result
        if error:
            data["error"] = error
        if progress:
            data["progress"] = progress
        await redis_cache.set(f"job:{job_id}", data, ttl=3600)


async def run_analysis_job(ctx, video_id: str, user_id: str, metadata: dict):
    redis_cache = await get_redis()
    job_id = await create_job(video_id, user_id, redis_cache)
    try:
        await update_job(job_id, redis_cache, JobStatus.processing, progress="Starting analysis")
        orchestrator = PipelineOrchestrator()
        result = await orchestrator.run(video_id, metadata)
        if result.result:
            await update_job(job_id, redis_cache, JobStatus.completed, result=result.result, progress="Completed")
        else:
            await update_job(job_id, redis_cache, JobStatus.failed, error="; ".join(result.errors), progress="Failed")
    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        await update_job(job_id, redis_cache, JobStatus.failed, error=str(e), progress="Failed")


try:
    from arq import create_pool
    from arq.connections import RedisSettings as ArqRedisSettings

    ARQ_AVAILABLE = True

    async def enqueue_arq(video_id: str, user_id: str, metadata: dict) -> str:
        redis_cache = await get_redis()
        job_id = await create_job(video_id, user_id, redis_cache)
        try:
            pool = await create_pool(ArqRedisSettings.from_dsn(settings.redis_url))
            await pool.enqueue_job("run_analysis_job", video_id, user_id, metadata)
            await pool.close()
        except Exception as e:
            logger.warning(f"arq enqueue failed, job stored without worker: {e}")
        return job_id

    class WorkerSettings:
        functions = [run_analysis_job]
        redis_settings = ArqRedisSettings.from_dsn(settings.redis_url) if settings.redis_url else None
        poll_delay = 1.0
        max_burst_jobs = 5

except ImportError:
    ARQ_AVAILABLE = False
    logger.info("arq not installed, async jobs will use manual polling")

    async def enqueue_arq(video_id: str, user_id: str, metadata: dict) -> str:
        redis_cache = await get_redis()
        return await create_job(video_id, user_id, redis_cache)
