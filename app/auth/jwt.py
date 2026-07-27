import time
from typing import Optional
import jwt
from app.config import settings

ACCESS_TOKEN_TTL = 1800
REFRESH_TOKEN_TTL = 604800


def create_access_token(user_id: str) -> str:
    return jwt.encode(
        {"sub": user_id, "iat": int(time.time()), "exp": int(time.time()) + ACCESS_TOKEN_TTL, "type": "access"},
        settings.jwt_secret,
        algorithm="HS256"
    )


def create_refresh_token(user_id: str) -> str:
    return jwt.encode(
        {"sub": user_id, "iat": int(time.time()), "exp": int(time.time()) + REFRESH_TOKEN_TTL, "type": "refresh"},
        settings.jwt_secret,
        algorithm="HS256"
    )


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except Exception:
        return None
