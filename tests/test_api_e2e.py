"""
End-to-end API tests.

These tests manually initialize app_state so they don't depend on lifespan.
"""

import tempfile
import os
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.deps import app_state
from app.data.database import Database
from app.data.cache import RedisCache


@pytest.fixture(scope="module", autouse=True)
def setup_app():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = Database(tmp.name)
    cache = RedisCache()
    app_state.init(db=db, cache=cache)
    yield
    conn = db._connect()
    conn.close()
    try:
        os.unlink(tmp.name)
    except PermissionError:
        pass


client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_register_and_login():
    email = f"e2e_{__import__('time').time()}@example.com"
    pw = "testpass123"

    resp = client.post("/auth/register", json={"email": email, "password": pw, "name": "E2E Test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["access_token"] is not None
    assert data["refresh_token"] is not None
    assert data["user_id"] is not None

    resp = client.post("/auth/login", json={"email": email, "password": pw})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["access_token"] is not None


def test_login_invalid_credentials():
    resp = client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["error"] is not None


def test_token_refresh():
    email = f"ref_{__import__('time').time()}@example.com"
    reg = client.post("/auth/register", json={"email": email, "password": "test1234", "name": "Refresh"})
    refresh_token = reg.json()["refresh_token"]

    resp = client.post("/auth/refresh", headers={"Authorization": f"Bearer {refresh_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["access_token"] is not None


def test_me_endpoint():
    email = f"me_{__import__('time').time()}@example.com"
    reg = client.post("/auth/register", json={"email": email, "password": "test1234", "name": "Me"})
    token = reg.json()["access_token"]

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == email


def test_history_requires_auth():
    resp = client.get("/api/v1/history")
    assert resp.status_code == 401


def test_feedback_without_auth():
    email = f"fb_{__import__('time').time()}@example.com"
    reg = client.post("/auth/register", json={"email": email, "password": "test1234", "name": "FB"})
    uid = reg.json()["user_id"]

    resp = client.post("/api/v1/feedback", json={"video_id": "test12345", "rating": "helpful"}, headers={"x-user-id": uid})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_analyze_invalid_video_id():
    email = f"an_{__import__('time').time()}@example.com"
    reg = client.post("/auth/register", json={"email": email, "password": "test1234", "name": "A"})
    token = reg.json()["access_token"]

    resp = client.post("/api/v1/analyze", json={"video_id": "ab"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422
