from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from app.pipeline.analyzer import Analyzer
from app.data.database import Database
from app.config import settings

router = APIRouter()
analyzer: Optional[Analyzer] = None
db: Optional[Database] = None


class AnalyzeRequest(BaseModel):
    video_id: str
    title: str = ""
    description: str = ""
    channel: str = ""
    hashtags: list[str] = []


class AnalyzeResponse(BaseModel):
    success: bool
    result: Optional[dict] = None
    error: Optional[str] = None


class FeedbackRequest(BaseModel):
    video_id: str
    rating: str


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_video(
    req: AnalyzeRequest,
    x_user_id: str = Header(default="anonymous")
):
    if not analyzer or not db:
        return AnalyzeResponse(success=False, error="Server not initialized")

    count = db.get_user_request_count(x_user_id)
    if count >= settings.max_analysis_per_day:
        return AnalyzeResponse(
            success=False,
            error=f"Daily limit of {settings.max_analysis_per_day} analyses reached"
        )

    try:
        metadata = {
            "title": req.title,
            "description": req.description,
            "channel": req.channel,
            "hashtags": req.hashtags
        }
        result = await analyzer.analyze(req.video_id, metadata, x_user_id)
        return AnalyzeResponse(success=True, result=result)
    except Exception as e:
        return AnalyzeResponse(success=False, error=str(e))


@router.get("/history")
async def get_history(
    x_user_id: str = Header(default="anonymous"),
    limit: int = 50
):
    if not db:
        return {"history": []}
    return {"history": db.get_history(x_user_id, limit)}


@router.post("/feedback")
async def submit_feedback(
    req: FeedbackRequest,
    x_user_id: str = Header(default="anonymous")
):
    if not db:
        return {"success": False}
    if req.rating not in ("helpful", "not_helpful", "incorrect"):
        raise HTTPException(400, "Rating must be: helpful, not_helpful, or incorrect")
    db.save_feedback(x_user_id, req.video_id, req.rating)
    return {"success": True}


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "openai_configured": bool(settings.openai_api_key),
        "gemini_configured": bool(settings.gemini_api_key)
    }
