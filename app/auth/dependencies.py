from fastapi import Header, HTTPException, Request
from typing import Optional
from app.auth.jwt import decode_token


async def get_current_user_id(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
) -> str:
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        payload = decode_token(token)
        if payload and "sub" in payload:
            return payload["sub"]
    if x_user_id:
        return x_user_id
    raise HTTPException(status_code=401, detail="Authentication required")


async def optional_user_id(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
) -> str:
    if authorization and authorization.startswith("Bearer "):
        payload = decode_token(authorization[7:])
        if payload and "sub" in payload:
            return payload["sub"]
    return x_user_id or "anonymous"
