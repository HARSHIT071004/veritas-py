from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.services.reasoning_service import ReasoningService
from app.services.trust_service import TrustService
from app.llm.client import call_llm, parse_json_response
from app.llm.prompt_loader import format_prompt
from app.pipeline.orchestrator import FAST_MODEL, ACCURATE_MODEL


class TrustScoreStage(PipelineStage):
    name = "trust_score"
    dependencies = ["claim_analysis", "evidence_retrieval", "context_builder"]

    def __init__(self):
        super().__init__()
        self._reasoning_svc = ReasoningService()
        self._trust_svc = TrustService()

    async def execute(self, ctx: StageContext, inputs: dict) -> StageResult:
        claim_data = inputs.get("claim_analysis", {})
        evidence_data = inputs.get("evidence_retrieval", {})
        context = inputs.get("context_builder", {})

        claims = claim_data.get("claims", [])
        video_summary = claim_data.get("video_summary", "") or context.get("video_summary", "")
        evidence_docs = evidence_data.get("evidence_docs", [])
        evidence_count = evidence_data.get("evidence_count", 0)

        model_override = FAST_MODEL if ctx.mode == "fast" else (ACCURATE_MODEL if ctx.mode == "accurate" else None)
        evidence_content = [d.get("content", "") for d in evidence_docs]

        if claim_data.get("combined_path"):
            reason_res_data = {
                "claim": claim_data.get("claim", ""),
                "verdict": claim_data.get("verdict", "unverifiable"),
                "confidence": claim_data.get("confidence", 0.0),
                "risk_level": claim_data.get("risk_level", "medium"),
                "explanation": claim_data.get("explanation", ""),
                "key_factors": claim_data.get("key_factors", []),
                "sources": claim_data.get("sources", []),
            }

            if evidence_docs:
                reason_res = await self._reasoning_svc.analyze(
                    claim=reason_res_data["claim"],
                    claim_category=claims[0].get("category", "") if claims else "",
                    transcript=context.get("transcript", ""),
                    ocr_text=context.get("ocr_text", ""),
                    evidence=evidence_content,
                    model_override=model_override,
                    video_summary=video_summary,
                    strict=True,
                )
                if reason_res:
                    reason_res_data = {
                        "claim": reason_res.claim,
                        "verdict": reason_res.verdict,
                        "confidence": reason_res.confidence,
                        "risk_level": reason_res.risk_level,
                        "explanation": reason_res.explanation,
                        "key_factors": reason_res.key_factors,
                        "sources": reason_res.sources,
                    }
        else:
            if not claims:
                full_text = ctx.metadata.get("title", "")
                reason_res = await self._reasoning_svc.analyze(
                    claim=full_text,
                    transcript=context.get("transcript", ""),
                    ocr_text=context.get("ocr_text", ""),
                    evidence=evidence_content,
                    model_override=model_override,
                    video_summary=video_summary,
                )
            else:
                reason_res = await self._reasoning_svc.analyze(
                    claim=claims[0].get("claim", ""),
                    claim_category=claims[0].get("category", ""),
                    transcript=context.get("transcript", ""),
                    ocr_text=context.get("ocr_text", ""),
                    evidence=evidence_content,
                    model_override=model_override,
                    video_summary=video_summary,
                )

            reason_res_data = {
                "claim": reason_res.claim,
                "verdict": reason_res.verdict,
                "confidence": reason_res.confidence,
                "risk_level": reason_res.risk_level,
                "explanation": reason_res.explanation,
                "key_factors": reason_res.key_factors,
                "sources": reason_res.sources,
            }

        reason_res_data = self._merge_web_sources(reason_res_data, evidence_docs)

        trust = self._trust_svc.calculate(
            verdict=reason_res_data["verdict"],
            llm_confidence=reason_res_data["confidence"],
            evidence_sources=[d.get("metadata", {}) for d in evidence_docs],
            evidence_count=evidence_count,
        )

        return StageResult(data={
            "claim": reason_res_data["claim"],
            "verdict": reason_res_data["verdict"],
            "confidence": reason_res_data["confidence"],
            "risk_level": reason_res_data["risk_level"],
            "explanation": reason_res_data["explanation"],
            "key_factors": reason_res_data["key_factors"],
            "sources": reason_res_data["sources"],
            "trust_score": trust.score,
            "trust_label": trust.label,
            "evidence_coverage": trust.evidence_coverage,
            "source_reliability": trust.source_reliability,
            "contradiction_count": trust.contradiction_count,
        })

    def _merge_web_sources(self, data: dict, evidence_docs: list[dict]) -> dict:
        sources = list(data.get("sources", []))
        existing_urls = set()
        for s in sources:
            if isinstance(s, dict) and s.get("url"):
                existing_urls.add(s["url"])

        for doc in evidence_docs:
            meta = doc.get("metadata", {})
            url = meta.get("url", "")
            if not url or url in existing_urls or meta.get("origin") != "web":
                continue
            sources.append({
                "title": meta.get("title", "") or meta.get("website", ""),
                "website": meta.get("website", ""),
                "url": url,
                "published": meta.get("published", ""),
            })
            existing_urls.add(url)

        data["sources"] = sources
        return data
