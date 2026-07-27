import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from fastapi import Query
from typing import Optional

from app.auth.dependencies import get_current_user_id, optional_user_id
from app.api.deps import get_analyzer, get_cache, get_db
from app.pipeline.analyzer import Analyzer
from app.data.database import Database
from app.data.cache import RedisCache
from app.config import settings

logger = logging.getLogger("clearlens.api")
router = APIRouter()


class AnalyzeRequest(BaseModel):
    video_id: str = Field(..., min_length=5, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    title: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=2000)
    channel: str = Field(default="", max_length=200)
    hashtags: list[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    success: bool
    result: Optional[dict] = None
    error: Optional[str] = None
    cached: bool = False


class JobSubmitResponse(BaseModel):
    success: bool
    job_id: Optional[str] = None
    status: str = "queued"
    error: Optional[str] = None


class FeedbackRequest(BaseModel):
    video_id: str = Field(..., min_length=5, max_length=100)
    rating: str = Field(..., pattern=r"^(helpful|not_helpful|incorrect)$")


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_video(
    req: AnalyzeRequest,
    user_id: str = Depends(get_current_user_id),
    analyzer: Analyzer = Depends(get_analyzer),
    db: Database = Depends(get_db),
    redis_cache: Optional[RedisCache] = Depends(get_cache),
):
    count = db.get_user_request_count(user_id)
    quota = db.get_user_quota(user_id)
    if count >= quota:
        return AnalyzeResponse(success=False, error=f"Daily limit of {quota} analyses reached")

    if redis_cache:
        cached = await redis_cache.get(f"result:{req.video_id}")
        if cached:
            logger.info("Redis cache hit", extra={"video_id": req.video_id, "user_id": user_id})
            return AnalyzeResponse(success=True, result=cached, cached=True)

    try:
        metadata = {"title": req.title, "description": req.description, "channel": req.channel, "hashtags": req.hashtags}
        result = await analyzer.analyze(req.video_id, metadata, user_id)
        if redis_cache:
            await redis_cache.set(f"result:{req.video_id}", result)
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
    count = db.get_user_request_count(user_id)
    quota = db.get_user_quota(user_id)
    if count >= quota:
        return JobSubmitResponse(success=False, error=f"Daily limit of {quota} analyses reached")
    if not redis_cache:
        return JobSubmitResponse(success=False, error="Async analysis requires Redis")

    job_id = f"job:{req.video_id}:{user_id[:8]}"
    await redis_cache.set(f"job:{job_id}", {"status": "queued", "video_id": req.video_id, "user_id": user_id}, ttl=3600)
    return JobSubmitResponse(success=True, job_id=job_id, status="queued")


@router.get("/result/{job_id}")
async def get_job_result(
    job_id: str,
    redis_cache: Optional[RedisCache] = Depends(get_cache),
):
    if not redis_cache:
        return {"status": "error", "error": "Redis not available"}
    data = await redis_cache.get(f"job:{job_id}")
    if not data:
        return {"status": "not_found", "error": "Job not found"}
    return {"status": data.get("status"), "result": data.get("result")}


@router.get("/history")
async def get_history(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(default=50, ge=1, le=200),
    db: Database = Depends(get_db),
):
    history = db.get_history(user_id, limit)
    return {"history": history, "total": len(history), "user_id": user_id}


@router.post("/feedback")
async def submit_feedback(
    req: FeedbackRequest,
    user_id: str = Depends(optional_user_id),
    db: Database = Depends(get_db),
):
    db.save_feedback(user_id, req.video_id, req.rating)
    logger.info("Feedback saved", extra={"user_id": user_id, "video_id": req.video_id, "rating": req.rating})
    return {"success": True}


@router.get("/health")
async def health(db: Database = Depends(get_db)):
    return {
        "status": "ok",
        "app": settings.app_name,
        "openai_configured": bool(settings.openai_api_key),
        "gemini_configured": bool(settings.gemini_api_key),
        "redis_enabled": settings.redis_enabled,
        "users_registered": db.get_user_count(),
    }
