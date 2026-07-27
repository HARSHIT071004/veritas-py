import pytest
from app.data.cache import RedisCache
from app.config import settings


def test_redis_cache_disabled_by_default():
    cache = RedisCache()
    assert cache._enabled is False


@pytest.mark.asyncio
async def test_redis_cache_get_returns_none_when_disabled():
    cache = RedisCache()
    result = await cache.get("test_key")
    assert result is None


@pytest.mark.asyncio
async def test_redis_cache_set_noop_when_disabled():
    cache = RedisCache()
    await cache.set("test_key", {"data": 123})
    result = await cache.get("test_key")
    assert result is None


def test_redis_cache_connection_lazy():
    cache = RedisCache()
    assert cache._client is None
    cache._connect()
    assert cache._enabled is False or cache._client is not None


def test_trust_score_zero():
    from app.pipeline.trust import TrustEngine
    engine = TrustEngine()
    score = engine.score("unverifiable", 0.0, [], 0)
    assert score.score == 0.0
    assert score.label == "very low"


def test_trust_score_high():
    from app.pipeline.trust import TrustEngine
    engine = TrustEngine()
    sources = [{"source_tier": 1, "contradicts": False}, {"source_tier": 1, "contradicts": False}]
    score = engine.score("true", 0.9, sources, 2)
    assert score.score > 0.5
    assert score.evidence_coverage > 0


def test_trust_score_contradiction_penalty():
    from app.pipeline.trust import TrustEngine
    engine = TrustEngine()
    good = [{"source_tier": 1, "contradicts": False}, {"source_tier": 1, "contradicts": False}]
    bad = [{"source_tier": 1, "contradicts": False}, {"source_tier": 1, "contradicts": True}]
    good_score = engine.score("true", 0.9, good, 2)
    bad_score = engine.score("true", 0.9, bad, 2)
    assert bad_score.score < good_score.score
