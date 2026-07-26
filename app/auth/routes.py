from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from typing import Optional
from app.auth.password import hash_password, verify_password
from app.auth.jwt import create_token, decode_token
from app.auth.dependencies import get_current_user_id

router = APIRouter(prefix="/auth", tags=["auth"])

_db = None


class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    name: str = Field(default="", max_length=100)


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., max_length=128)


class AuthResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    user_id: Optional[str] = None
    error: Optional[str] = None


@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    global _db
    if not _db:
        return AuthResponse(success=False, error="Server not ready")
    existing = _db.get_user_by_email(req.email)
    if existing:
        return AuthResponse(success=False, error="Email already registered")
    user_id = _db.create_user(req.email, hash_password(req.password), req.name)
    token = create_token(user_id)
    return AuthResponse(success=True, token=token, user_id=user_id)


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    global _db
    if not _db:
        return AuthResponse(success=False, error="Server not ready")
    user = _db.get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        return AuthResponse(success=False, error="Invalid email or password")
    token = create_token(user["id"])
    return AuthResponse(success=True, token=token, user_id=user["id"])


@router.post("/refresh", response_model=AuthResponse)
async def refresh(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        return AuthResponse(success=False, error="No token provided")
    payload = decode_token(authorization[7:])
    if not payload:
        return AuthResponse(success=False, error="Invalid or expired token")
    new_token = create_token(payload["sub"])
    return AuthResponse(success=True, token=new_token, user_id=payload["sub"])


@router.get("/me")
async def get_me(user_id: str = Depends(get_current_user_id)):
    global _db
    if not _db:
        return {"error": "Server not ready"}
    user = _db.get_user(user_id)
    if not user:
        return {"error": "User not found"}
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


def init_routes(db):
    global _db
    _db = db
