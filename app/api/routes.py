import asyncio
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from fastapi import Query
from typing import Optional

from app.auth.dependencies import get_current_user_id, optional_user_id
from app.api.deps import get_analyzer, get_cache, get_db, get_pipeline_cache
from app.pipeline.analyzer import Analyzer
from app.pipeline.cache import MultiLevelCache
from app.data.database import Database
from app.data.cache import RedisCache
from app.data.repositories.analysis_repository import AnalysisRepository
from app.data.repositories.user_repository import UserRepository
from app.schemas.job import JobSubmitResponse, JobResultResponse
from app.worker import create_job, get_job
from app.config import settings

logger = logging.getLogger("clearlens.api")
router = APIRouter()


class AnalyzeRequest(BaseModel):
    video_id: str = Field(..., min_length=5, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    title: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=2000)
    channel: str = Field(default="", max_length=200)
    hashtags: list[str] = Field(default_factory=list)
    mode: str = Field(default="balanced", pattern=r"^(fast|balanced|accurate)$")


class AnalyzeResponse(BaseModel):
    success: bool
    result: Optional[dict] = None
    error: Optional[str] = None
    cached: bool = False


class FeedbackRequest(BaseModel):
    video_id: str = Field(..., min_length=5, max_length=100)
    rating: str = Field(..., pattern=r"^(helpful|not_helpful|incorrect)$")


class PrefetchRequest(BaseModel):
    video_id: str = Field(..., min_length=5, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    background: bool = False


_in_flight_prefetch: set[str] = set()


@router.post("/prefetch")
async def prefetch_video(
    req: PrefetchRequest,
    pipeline_cache: MultiLevelCache = Depends(get_pipeline_cache),
    redis_cache: Optional[RedisCache] = Depends(get_cache),
    db: Database = Depends(get_db),
):
    vid = req.video_id

    if vid in _in_flight_prefetch:
        logger.info(f"Prefetch already in flight for {vid}, skipping")
        return {"success": True, "video_id": vid, "status": "already_in_flight"}

    cached = await pipeline_cache.get("transcript", vid)
    if cached:
        logger.info(f"Prefetch cache hit for {vid}, skipping")
        return {"success": True, "video_id": vid, "status": "cached"}

    _in_flight_prefetch.add(vid)
    try:
        from app.services.transcript_service import TranscriptService

        ts = TranscriptService()

        asyncio.ensure_future(_safe_prefetch_transcript(ts, vid, pipeline_cache))
        asyncio.ensure_future(_safe_prefetch_metadata(ts, vid, pipeline_cache))

        if req.background:
            analyzer = get_analyzer()
            asyncio.ensure_future(_safe_prefetch_analysis(analyzer, vid))

        return {"success": True, "video_id": vid, "status": "prefetching"}
    finally:
        _in_flight_prefetch.discard(vid)


async def _safe_prefetch_transcript(ts, video_id: str, cache: MultiLevelCache):
    try:
        result = await ts.extract(video_id)
        if result.text:
            await cache.set("transcript", {
                "text": result.text,
                "source": result.source,
                "language": result.language,
                "duration": result.duration,
                "available": True,
            }, video_id)
            logger.info(f"Prefetched transcript for {video_id}")
    except Exception as e:
        logger.debug(f"Prefetch transcript failed for {video_id}: {e}")


async def _safe_prefetch_metadata(ts, video_id: str, cache: MultiLevelCache):
    try:
        meta = await ts.get_metadata(video_id)
        if meta:
            await cache.set("metadata", meta, video_id)
            logger.info(f"Prefetched metadata for {video_id}")
    except Exception as e:
        logger.debug(f"Prefetch metadata failed for {video_id}: {e}")


async def _safe_prefetch_analysis(analyzer, video_id: str):
    try:
        await analyzer.analyze(video_id, {}, "background", mode="fast", prefetched=True)
    except Exception as e:
        logger.debug(f"Prefetch analysis failed for {video_id}: {e}")


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_video(
    req: AnalyzeRequest,
    user_id: str = Depends(get_current_user_id),
    analyzer: Analyzer = Depends(get_analyzer),
    db: Database = Depends(get_db),
    redis_cache: Optional[RedisCache] = Depends(get_cache),
    pipeline_cache: MultiLevelCache = Depends(get_pipeline_cache),
):
    users = UserRepository(db)
    quota = users.get_quota(user_id)
    count = users.get_request_count(user_id)
    if count >= quota:
        return AnalyzeResponse(success=False, error=f"Daily limit of {quota} analyses reached")

    if redis_cache:
        cached = await redis_cache.get(f"analysis:{req.video_id}")
        if cached:
            logger.info("Redis cache hit", extra={"video_id": req.video_id, "user_id": user_id})
            return AnalyzeResponse(success=True, result=cached, cached=True)

    try:
        metadata = {"title": req.title, "description": req.description, "channel": req.channel, "hashtags": req.hashtags}
        result = await analyzer.analyze(req.video_id, metadata, user_id, mode=req.mode)
        if redis_cache:
            await redis_cache.set(f"analysis:{req.video_id}", result, ttl=600)
        return AnalyzeResponse(success=True, result=result)
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True, extra={"video_id": req.video_id, "user_id": user_id})
        return AnalyzeResponse(success=False, error=str(e))


@router.post("/analyze/async", response_model=JobSubmitResponse)
async def analyze_video_async(
    req: AnalyzeRequest,
    user_id: str = Depends(get_current_user_id),
    db: Database = Depends(get_db),
    redis_cache: Optional[RedisCache] = Depends(get_cache),
):
    users = UserRepository(db)
    quota = users.get_quota(user_id)
    count = users.get_request_count(user_id)
    if count >= quota:
        return JobSubmitResponse(success=False, error=f"Daily limit of {quota} analyses reached")
    if not redis_cache:
        return JobSubmitResponse(success=False, error="Async analysis requires Redis")

    metadata = {"title": req.title, "description": req.description, "channel": req.channel, "hashtags": req.hashtags, "mode": req.mode}
    job_id = await create_job(req.video_id, user_id, redis_cache)
    return JobSubmitResponse(success=True, job_id=job_id, status="queued")


@router.get("/result/{job_id}", response_model=JobResultResponse)
async def get_job_result(
    job_id: str,
    redis_cache: Optional[RedisCache] = Depends(get_cache),
):
    if not redis_cache:
        return JobResultResponse(status="error", error="Redis not available")
    job = await get_job(job_id, redis_cache)
    if job.status.value == "failed" and job.error:
        return JobResultResponse(status="failed", error=job.error)
    if job.status.value == "completed":
        return JobResultResponse(status="completed", result=job.result)
    return JobResultResponse(status=job.status.value)


@router.get("/history")
async def get_history(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(default=50, ge=1, le=200),
    db: Database = Depends(get_db),
):
    repo = AnalysisRepository(db)
    history = repo.get_history(user_id, limit)
    return {"history": history, "total": len(history), "user_id": user_id}


@router.post("/feedback")
async def submit_feedback(
    req: FeedbackRequest,
    user_id: str = Depends(optional_user_id),
    db: Database = Depends(get_db),
):
    repo = AnalysisRepository(db)
    repo.save_feedback(user_id, req.video_id, req.rating)
    logger.info("Feedback saved", extra={"user_id": user_id, "video_id": req.video_id, "rating": req.rating})
    return {"success": True}


@router.get("/health")
async def health(db: Database = Depends(get_db)):
    users = UserRepository(db)
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "version": "1.0.0",
            "uptime_seconds": 0,
            "dependencies": {
                "sqlite": "connected" if db else "disconnected",
            },
        },
    }


@router.get("/ready")
async def ready(db: Database = Depends(get_db)):
    deps = {
        "sqlite": {"status": "connected" if db else "disconnected", "latency_ms": 1},
    }
    all_ready = all(d["status"] == "connected" for d in deps.values())
    if all_ready:
        return {"success": True, "data": {"status": "ready", "dependencies": deps}}
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=503,
        content={"success": False, "data": {"status": "not_ready", "dependencies": deps}},
    )


@router.get("/live")
async def live():
    from datetime import datetime, timezone
    return {
        "success": True,
        "data": {
            "status": "alive",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
