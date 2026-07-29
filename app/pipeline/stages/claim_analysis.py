from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.services.claim_service import ClaimService
from app.services.classifier_service import ClassifierService
from app.llm.client import call_llm, parse_json_response
from app.llm.prompt_loader import format_prompt
from app.schemas.pipeline_models import Claim
from app.pipeline.orchestrator import FAST_MODEL, ACCURATE_MODEL


class ClaimAnalysisStage(PipelineStage):
    name = "claim_analysis"
    dependencies = ["context_builder"]

    def __init__(self):
        super().__init__()
        self._claims_svc = ClaimService()
        self._classifier_svc = ClassifierService()

    async def execute(self, ctx: StageContext, inputs: dict) -> StageResult:
        context = inputs.get("context_builder", {})
        transcript = context.get("transcript", "")
        ocr_text = context.get("ocr_text", "")
        title = context.get("title", "")
        description = context.get("description", "")
        channel = context.get("channel", "")

        combined_res = None
        if transcript:
            combined_res = await self._run_combined_analysis(transcript, context, ctx.mode)

        if combined_res:
            return StageResult(data={
                "claims": [c.model_dump() for c in combined_res["claims_res"].claims],
                "video_summary": combined_res["claims_res"].video_summary,
                "extraction_ms": combined_res["extraction_ms"],
                "classification_ms": combined_res["classification_ms"],
                "reasoning_ms": combined_res["reasoning_ms"],
                "claim": combined_res["reason_res"].claim,
                "verdict": combined_res["reason_res"].verdict,
                "confidence": combined_res["reason_res"].confidence,
                "risk_level": combined_res["reason_res"].risk_level,
                "explanation": combined_res["reason_res"].explanation,
                "key_factors": combined_res["reason_res"].key_factors,
                "sources": combined_res["reason_res"].sources,
                "combined_path": True,
            })

        model_override = FAST_MODEL if ctx.mode == "fast" else (ACCURATE_MODEL if ctx.mode == "accurate" else None)

        if ctx.mode == "accurate":
            claims_res = await self._claims_svc.extract(
                transcript=transcript, ocr_text=ocr_text,
                title=title, description=description, channel=channel,
                model_override=model_override
            )
        else:
            claims_res = await self._claims_svc.extract(
                transcript=transcript, ocr_text=ocr_text,
                title=title, description=description, channel=channel
            )

        if claims_res.error:
            return StageResult(success=False, error=claims_res.error, data={
                "claims": [], "video_summary": "", "combined_path": False,
                "extraction_ms": 0, "classification_ms": 0, "reasoning_ms": 0,
            })

        claim_texts = [c.claim for c in claims_res.claims]
        if claim_texts:
            if ctx.mode == "accurate":
                class_res = await self._classifier_svc.classify(claim_texts, model_override=model_override)
            else:
                class_res = await self._classifier_svc.classify(claim_texts)
            for i, claim in enumerate(claims_res.claims):
                if i < len(class_res.classifications):
                    claim.category = class_res.classifications[i].category
                    claim.classifier_confidence = class_res.classifications[i].confidence
                else:
                    claim.category = "general"

        return StageResult(data={
            "claims": [c.model_dump() for c in claims_res.claims],
            "video_summary": claims_res.video_summary,
            "combined_path": False,
        })

    async def _run_combined_analysis(self, transcript: str, context: dict, mode: str) -> dict | None:
        import time
        t_start = time.time()
        try:
            from app.pipeline.orchestrator import FAST_MODEL, ACCURATE_MODEL
            model_override = FAST_MODEL if mode == "fast" else (ACCURATE_MODEL if mode == "accurate" else None)
            prompt = format_prompt("combined_analysis",
                transcript=transcript[:4000],
                title=context.get("title", "")[:200],
                channel=context.get("channel", "")[:100]
            )
            content = await call_llm(prompt, max_tokens=3000, temperature=0.1, model_override=model_override)
            if not content:
                return None
            parsed = parse_json_response(content)
            if not parsed or "claims" not in parsed:
                return None

            claims_data = parsed["claims"]
            if not claims_data:
                return None

            from app.schemas.pipeline_models import Claim, ClaimExtractionResult, ReasoningResult
            claim_objects = []
            for c in claims_data:
                claim_objects.append(Claim(
                    claim=c.get("claim", ""),
                    risk_level=c.get("risk_level", "low"),
                    requires_verification=True,
                    context="",
                    category=c.get("category", "general"),
                    classifier_confidence=c.get("confidence", 0.5),
                ))

            first = claims_data[0]
            reason_res = ReasoningResult(
                claim=first.get("claim", "")[:200],
                verdict=first.get("verdict", "unverifiable"),
                confidence=first.get("confidence", 0.0),
                risk_level=first.get("risk_level", "medium"),
                explanation=first.get("explanation", ""),
                key_factors=first.get("key_factors", ["Analysis completed", "Combined pipeline"]),
                sources=first.get("sources", [])
            )

            elapsed = int((time.time() - t_start) * 1000)
            return {
                "claims_res": ClaimExtractionResult(claims=claim_objects, video_summary=parsed.get("video_summary", "")),
                "reason_res": reason_res,
                "extraction_ms": elapsed // 2,
                "classification_ms": 0,
                "reasoning_ms": elapsed // 2,
            }
        except Exception as e:
            return None
