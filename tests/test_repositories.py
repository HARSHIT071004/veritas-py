import tempfile
import os
import pytest
from app.data.database import Database
from app.data.repositories.user_repository import UserRepository
from app.data.repositories.analysis_repository import AnalysisRepository
from app.data.models import AnalysisResult


@pytest.fixture
def db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    d = Database(tmp.name)
    yield d
    conn = d._connect()
    conn.close()
    try:
        os.unlink(tmp.name)
    except PermissionError:
        pass


def _unique_email(prefix: str = "test") -> str:
    import time
    return f"{prefix}_{int(time.time() * 1000000)}@example.com"


def test_user_repository_create_and_get(db):
    repo = UserRepository(db)
    email = _unique_email("create")
    user_id = repo.create(email, "hashed_pw", "Test User")
    assert user_id is not None

    user = repo.get_by_id(user_id)
    assert user is not None
    assert user["email"] == email
    assert user["name"] == "Test User"


def test_user_repository_get_by_email(db):
    repo = UserRepository(db)
    email_a = _unique_email("alice")
    email_b = _unique_email("bob")
    repo.create(email_a, "hash1", "Alice")
    repo.create(email_b, "hash2", "Bob")

    user = repo.get_by_email(email_a)
    assert user is not None
    assert user["name"] == "Alice"


def test_user_repository_get_by_email_not_found(db):
    repo = UserRepository(db)
    user = repo.get_by_email("nonexistent@example.com")
    assert user is None


def test_user_repository_quota(db):
    repo = UserRepository(db)
    user_id = repo.create(_unique_email("quota"), "hash", "Quota")
    count = repo.get_request_count(user_id)
    assert count >= 0
    quota = repo.get_quota(user_id)
    assert quota > 0


def test_user_repository_count(db):
    repo = UserRepository(db)
    repo.create(_unique_email("count_a"), "h1", "A")
    repo.create(_unique_email("count_b"), "h2", "B")
    assert repo.get_count() >= 2


def test_analysis_repository_cache(db):
    repo = AnalysisRepository(db)
    repo.set_cache("video_001", {"verdict": "true", "confidence": 0.9})
    cached = repo.get_cached("video_001")
    assert cached is not None
    assert cached["verdict"] == "true"


def test_analysis_repository_cache_miss(db):
    repo = AnalysisRepository(db)
    cached = repo.get_cached("nonexistent_video")
    assert cached is None


def test_analysis_repository_history(db):
    repo = AnalysisRepository(db)
    users = UserRepository(db)
    user_id = users.create(_unique_email("hist"), "hash", "History")

    result = AnalysisResult(video_id="v001", user_id=user_id, claim="test claim", verdict="true", confidence=0.8, explanation="test", sources=[], transcript_used=True, ocr_used=False, processing_time_ms=100)
    repo.save_history(result)

    history = repo.get_history(user_id)
    assert len(history) >= 1
    assert history[0]["video_id"] == "v001"


def test_analysis_repository_history_limit(db):
    repo = AnalysisRepository(db)
    users = UserRepository(db)
    user_id = users.create(_unique_email("hist2"), "hash", "History2")

    for i in range(5):
        result = AnalysisResult(video_id=f"v{i:03d}", user_id=user_id, claim="c", verdict="true", confidence=0.5, explanation="e", sources=[], transcript_used=True, ocr_used=False, processing_time_ms=10)
        repo.save_history(result)

    history = repo.get_history(user_id, limit=2)
    assert len(history) == 2


def test_analysis_repository_feedback_valid_user(db):
    repo = AnalysisRepository(db)
    users = UserRepository(db)
    user_id = users.create(_unique_email("fb"), "hash", "FB")
    repo.save_feedback(user_id, "video_y", "helpful")
