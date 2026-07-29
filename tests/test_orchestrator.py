import pytest
from app.schemas.pipeline_models import PipelineResult, PipelineTimings


@pytest.mark.asyncio
async def test_pipeline_result_model():
    timings = PipelineTimings(transcript_ms=100, extraction_ms=200, classification_ms=150, reasoning_ms=300, total_ms=750)
    result = PipelineResult(analysis_id="abc123", video_id="vid123", status="completed", result={"verdict": "true"}, timings=timings, errors=[])
    assert result.analysis_id == "abc123"
    assert result.status == "completed"
    assert result.result["verdict"] == "true"


@pytest.mark.asyncio
async def test_pipeline_result_failed():
    timings = PipelineTimings()
    result = PipelineResult(analysis_id="abc", video_id="vid", status="failed", result=None, timings=timings, errors=["transcript failed"])
    assert result.status == "failed"
    assert len(result.errors) == 1


def test_trust_service_direct():
    from app.services.trust_service import TrustService
    service = TrustService()
    score = service.calculate(verdict="true", llm_confidence=0.8, evidence_sources=[{"source_tier": 1}], evidence_count=1)
    assert score.score > 0
    assert score.label is not None


def test_transcript_service_imports():
    from app.services.transcript_service import TranscriptService
    svc = TranscriptService()
    assert svc is not None
