from fastapi import Header, HTTPException, Request, status
from typing import Optional
from app.config import settings


async def get_current_user_id(
    x_internal_key: str = Header(None, alias="X-Internal-Key"),
    x_user_id: str = Header(None, alias="X-User-Id"),
) -> str:
    if x_internal_key != settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )
    return x_user_id or "anonymous"


async def optional_user_id(
    x_internal_key: str = Header(None, alias="X-Internal-Key"),
    x_user_id: str = Header(None, alias="X-User-Id"),
) -> str:
    if x_internal_key == settings.internal_api_key:
        return x_user_id or "anonymous"
    return "anonymous"
