import time
import hmac
import hashlib
import base64
import json
from typing import Optional
from app.config import settings


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def create_token(user_id: str, secret: Optional[str] = None) -> str:
    sec = secret or settings.jwt_secret
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps({
        "sub": user_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + settings.jwt_expiry_seconds
    }).encode())
    sig = _b64(hmac.new(sec.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def decode_token(token: str, secret: Optional[str] = None) -> Optional[dict]:
    sec = secret or settings.jwt_secret
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        expected_sig = _b64(hmac.new(sec.encode(), f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(parts[2], expected_sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
