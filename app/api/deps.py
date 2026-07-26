from fastapi import Header, HTTPException
from app.config import settings


async def verify_rate_limit(
    x_user_id: str = Header(default="anonymous"),
    db=None
):
    if not db:
        return x_user_id
    count = db.get_user_request_count(x_user_id)
    if count >= settings.max_analysis_per_day:
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit of {settings.max_analysis_per_day} analyses reached"
        )
    return x_user_id
