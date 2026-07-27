from app.schemas.pipeline_models import TrustScore

TIER_WEIGHTS = {1: 1.0, 2: 0.8, 3: 0.6}
VERDICT_CONFIDENCE_MAP = {
    "true": 0.7,
    "false": 0.8,
    "misleading": 0.6,
    "unverifiable": 0.3,
}


class TrustService:
    def calculate(self, verdict: str, llm_confidence: float, evidence_sources: list[dict] = None, evidence_count: int = 0) -> TrustScore:
        evidence_sources = evidence_sources or []
        evidence_coverage = min(evidence_count / 5, 1.0) if evidence_sources else 0.0

        total_weight = 0.0
        weighted_sum = 0.0
        contradictions = 0
        for src in evidence_sources:
            tier = src.get("source_tier", 3)
            weight = TIER_WEIGHTS.get(tier, 0.6)
            total_weight += weight
            weighted_sum += weight * tier
            if src.get("contradicts", False):
                contradictions += 1

        source_reliability = 1.0 - (weighted_sum / total_weight / 3) if total_weight > 0 else (0.0 if evidence_count == 0 else 0.3)

        base = llm_confidence * VERDICT_CONFIDENCE_MAP.get(verdict, 0.4)
        adjusted = base * (0.4 + 0.3 * evidence_coverage + 0.3 * source_reliability)
        adjusted *= max(0.5, 1.0 - contradictions * 0.2)
        adjusted = max(0.0, min(1.0, adjusted))

        label = self._label(adjusted)
        factors = self._factors(verdict, llm_confidence, evidence_coverage, source_reliability, contradictions)

        return TrustScore(score=round(adjusted, 2), label=label, evidence_coverage=evidence_coverage, source_reliability=source_reliability, contradiction_count=contradictions)

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

    def _factors(self, verdict: str, llm_conf: float, coverage: float, reliability: float, contradictions: int) -> list[str]:
        factors = []
        if llm_conf >= 0.7:
            factors.append("high confidence reasoning")
        elif llm_conf >= 0.4:
            factors.append("moderate confidence reasoning")
        else:
            factors.append("low confidence reasoning")
        if coverage >= 0.8:
            factors.append("strong evidence coverage")
        elif coverage >= 0.4:
            factors.append("partial evidence coverage")
        elif coverage == 0:
            factors.append("no external evidence")
        if reliability >= 0.7:
            factors.append("reliable sources")
        elif reliability < 0.3 and reliability > 0:
            factors.append("low source reliability")
        if contradictions > 0:
            factors.append(f"{contradictions} contradictory source(s)")
        if verdict == "unverifiable":
            factors.append("insufficient evidence for verdict")
        return factors
