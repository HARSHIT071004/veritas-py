import pytest
from app.pipeline.trust import TrustEngine


def test_trust_score_zero_when_no_evidence():
    engine = TrustEngine()
    score = engine.score("unverifiable", 0.0, [], 0)
    assert score.score == 0.0
    assert score.label == "very low"


def test_trust_score_high_with_good_evidence():
    engine = TrustEngine()
    sources = [
        {"source_tier": 1, "contradicts": False},
        {"source_tier": 1, "contradicts": False},
        {"source_tier": 2, "contradicts": False},
    ]
    score = engine.score("true", 0.9, sources, 3)
    assert score.score > 0.5
    assert score.evidence_coverage > 0


def test_trust_score_drops_with_contradictions():
    engine = TrustEngine()
    good = [
        {"source_tier": 1, "contradicts": False},
        {"source_tier": 1, "contradicts": False},
    ]
    bad = [
        {"source_tier": 1, "contradicts": False},
        {"source_tier": 1, "contradicts": True},
    ]
    good_score = engine.score("true", 0.9, good, 2)
    bad_score = engine.score("true", 0.9, bad, 2)
    assert bad_score.score < good_score.score


def test_trust_label_thresholds():
    engine = TrustEngine()
    assert engine._label(0.95) == "very high"
    assert engine._label(0.80) == "high"
    assert engine._label(0.55) == "medium"
    assert engine._label(0.30) == "low"
    assert engine._label(0.10) == "very low"
