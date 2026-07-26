import logging
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from fastapi import Query
from typing import Optional

from app.auth.dependencies import get_current_user_id, optional_user_id
from app.pipeline.analyzer import Analyzer
from app.data.database import Database
from app.data.cache import RedisCache
from app.config import settings

logger = logging.getLogger("clearlens.api")
router = APIRouter()

analyzer: Optional[Analyzer] = None
db: Optional[Database] = None
redis_cache: Optional[RedisCache] = None


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


class FeedbackRequest(BaseModel):
    video_id: str = Field(..., min_length=5, max_length=100)
    rating: str = Field(..., pattern=r"^(helpful|not_helpful|incorrect)$")


class ErrorResponse(BaseModel):
    success: bool = False
    error: str


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_video(
    req: AnalyzeRequest,
    user_id: str = Depends(get_current_user_id)
):
    if not analyzer or not db:
        return AnalyzeResponse(success=False, error="Server not initialized")

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
        metadata = {
            "title": req.title,
            "description": req.description,
            "channel": req.channel,
            "hashtags": req.hashtags
        }
        result = await analyzer.analyze(req.video_id, metadata, user_id)

        if redis_cache:
            await redis_cache.set(f"result:{req.video_id}", result)

        return AnalyzeResponse(success=True, result=result)
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True, extra={"video_id": req.video_id, "user_id": user_id})
        return AnalyzeResponse(success=False, error=str(e))


@router.get("/history")
async def get_history(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(default=50, ge=1, le=200)
):
    if not db:
        return {"history": []}
    history = db.get_history(user_id, limit)
    return {"history": history, "total": len(history), "user_id": user_id}


@router.post("/feedback")
async def submit_feedback(
    req: FeedbackRequest,
    user_id: str = Depends(optional_user_id)
):
    if not db:
        return {"success": False}
    db.save_feedback(user_id, req.video_id, req.rating)
    logger.info("Feedback saved", extra={"user_id": user_id, "video_id": req.video_id, "rating": req.rating})
    return {"success": True}


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "openai_configured": bool(settings.openai_api_key),
        "gemini_configured": bool(settings.gemini_api_key),
        "redis_enabled": settings.redis_enabled,
        "users_registered": db.get_user_count() if db else 0
    }


def init_routes(a, d, rc=None):
    global analyzer, db, redis_cache
    analyzer = a
    db = d
    redis_cache = rc
