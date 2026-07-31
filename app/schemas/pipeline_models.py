from pydantic import BaseModel, Field
from typing import Optional


class TranscriptResult(BaseModel):
    text: Optional[str] = None
    language: Optional[str] = None
    duration: int = 0
    source: Optional[str] = None
    error: Optional[str] = None


class Claim(BaseModel):
    claim: str
    risk_level: str = "low"
    requires_verification: bool = True
    context: str = ""
    category: str = "general"
    classifier_confidence: float = 0.5


class ClaimExtractionResult(BaseModel):
    claims: list[Claim] = []
    video_summary: str = ""
    error: Optional[str] = None


class ClassificationItem(BaseModel):
    claim_index: int
    category: str
    confidence: float


class ClassificationResult(BaseModel):
    classifications: list[ClassificationItem] = []


class ReasoningResult(BaseModel):
    claim: str = ""
    verdict: str = "unverifiable"
    confidence: float = 0.0
    risk_level: str = "medium"
    explanation: str = ""
    key_factors: list[str] = []
    sources: list[dict] = []


class TrustScore(BaseModel):
    score: float = 0.0
    label: str = "very low"
    evidence_coverage: float = 0.0
    source_reliability: float = 0.0
    contradiction_count: int = 0


class PipelineTimings(BaseModel):
    transcript_ms: int = 0
    extraction_ms: int = 0
    classification_ms: int = 0
    reasoning_ms: int = 0
    total_ms: int = 0


class PipelineResult(BaseModel):
    analysis_id: str = ""
    video_id: str = ""
    status: str = "completed"
    result: Optional[dict] = None
    timings: PipelineTimings = PipelineTimings()
    errors: list[str] = []
