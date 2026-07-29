import pytest
from app.auth.password import hash_password, verify_password
from app.auth.jwt import create_access_token, create_refresh_token, decode_token


def test_password_hashing():
    pw = "test_password_123"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed)


def test_password_wrong():
    hashed = hash_password("correct")
    assert not verify_password("wrong", hashed)


def test_access_token():
    user_id = "user_abc123"
    token = create_access_token(user_id)
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["type"] == "access"


def test_refresh_token():
    user_id = "user_abc123"
    token = create_refresh_token(user_id)
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["type"] == "refresh"


def test_invalid_token():
    payload = decode_token("invalid_token_here")
    assert payload is None


def test_expired_token():
    import jwt
    from app.config import settings
    token = jwt.encode({"sub": "test", "type": "access", "exp": 0}, settings.jwt_secret, algorithm="HS256")
    payload = decode_token(token)
    assert payload is None
