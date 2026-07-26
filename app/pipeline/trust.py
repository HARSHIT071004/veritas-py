from dataclasses import dataclass
from typing import Optional


@dataclass
class TrustScore:
    score: float
    label: str
    evidence_coverage: float
    source_reliability: float
    contradiction_count: int


class TrustEngine:
    TIER_WEIGHTS = {1: 1.0, 2: 0.8, 3: 0.6}

    def score(self, verdict: str, llm_confidence: float, evidence_sources: list[dict], evidence_count: int) -> TrustScore:
        if not evidence_sources or evidence_count == 0:
            return TrustScore(0.0, "very low", 0.0, 0.0, 0)

        evidence_coverage = min(evidence_count / 5, 1.0)

        total_weight = 0.0
        weighted_sum = 0.0
        for src in evidence_sources:
            tier = src.get("source_tier", 3)
            weight = self.TIER_WEIGHTS.get(tier, 0.6)
            total_weight += weight
            weighted_sum += weight * tier

        source_reliability = 1.0 - (weighted_sum / total_weight / 3) if total_weight > 0 else 0.3

        contradictions = sum(
            1 for s in evidence_sources
            if s.get("contradicts", False)
        )

        base = llm_confidence
        adjusted = base * (0.4 + 0.3 * evidence_coverage + 0.3 * source_reliability)
        adjusted *= max(0.5, 1.0 - contradictions * 0.2)
        adjusted = max(0.0, min(1.0, adjusted))

        label = self._label(adjusted)
        return TrustScore(round(adjusted, 2), label, evidence_coverage, source_reliability, contradictions)

    def _label(self, score: float) -> str:
        if score >= 0.9:
            return "very high"
        if score >= 0.7:
            return "high"
        if score >= 0.4:
            return "medium"
        if score >= 0.2:
            return "low"
        return "very low"
