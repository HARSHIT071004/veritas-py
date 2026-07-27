from fastapi import APIRouter, Header, Depends
from pydantic import BaseModel, Field
from typing import Optional
from app.auth.password import hash_password, verify_password
from app.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.auth.dependencies import get_current_user_id
from app.api.deps import get_db
from app.data.database import Database
from app.data.repositories.user_repository import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    name: str = Field(default="", max_length=100)


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., max_length=128)


class AuthResponse(BaseModel):
    success: bool
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    user_id: Optional[str] = None
    error: Optional[str] = None


@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest, db: Database = Depends(get_db)):
    users = UserRepository(db)
    existing = users.get_by_email(req.email)
    if existing:
        return AuthResponse(success=False, error="Email already registered")
    user_id = users.create(req.email, hash_password(req.password), req.name)
    return AuthResponse(success=True, access_token=create_access_token(user_id), refresh_token=create_refresh_token(user_id), user_id=user_id)


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: Database = Depends(get_db)):
    users = UserRepository(db)
    user = users.get_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        return AuthResponse(success=False, error="Invalid email or password")
    return AuthResponse(success=True, access_token=create_access_token(user["id"]), refresh_token=create_refresh_token(user["id"]), user_id=user["id"])


@router.post("/refresh", response_model=AuthResponse)
async def refresh(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        return AuthResponse(success=False, error="No token provided")
    payload = decode_token(authorization[7:])
    if not payload:
        return AuthResponse(success=False, error="Invalid or expired token")
    if payload.get("type") != "refresh":
        return AuthResponse(success=False, error="Invalid token type")
    return AuthResponse(success=True, access_token=create_access_token(payload["sub"]), refresh_token=create_refresh_token(payload["sub"]), user_id=payload["sub"])


@router.get("/me")
async def get_me(user_id: str = Depends(get_current_user_id), db: Database = Depends(get_db)):
    users = UserRepository(db)
    user = users.get_by_id(user_id)
    if not user:
        return {"error": "User not found"}
    return {"id": user["id"], "email": user["email"], "name": user["name"]}
