import time
import asyncio
import logging
import uuid
from typing import Optional
from app.services.transcript_service import TranscriptService
from app.services.claim_service import ClaimService
from app.services.classifier_service import ClassifierService
from app.services.reasoning_service import ReasoningService
from app.services.trust_service import TrustService
from app.schemas.pipeline_models import PipelineResult, PipelineTimings

logger = logging.getLogger("clearlens.orchestrator")


class PipelineOrchestrator:
    def __init__(self):
        self.transcript = TranscriptService()
        self.claims = ClaimService()
        self.classifier = ClassifierService()
        self.reasoning = ReasoningService()
        self.trust = TrustService()

    async def run(self, video_id: str, metadata: dict) -> PipelineResult:
        analysis_id = uuid.uuid4().hex[:12]
        timings = PipelineTimings()
        errors = []
        result_dict = None

        try:
            # Phase 1: Transcript + Vision (parallel)
            t0 = time.time()
            transcript_task = self.transcript.extract(video_id)
            vision_task = self._extract_vision(video_id, metadata.get("title", ""))
            transcript_res, vision_res = await asyncio.gather(transcript_task, vision_task, return_exceptions=True)

            transcript = getattr(transcript_res, "text", None) if not isinstance(transcript_res, Exception) else None
            transcript_source = getattr(transcript_res, "source", None) if not isinstance(transcript_res, Exception) else None
            ocr_text = vision_res.get("ocr_text") if isinstance(vision_res, dict) else None
            ocr_used = vision_res.get("used", False) if isinstance(vision_res, dict) else False

            if isinstance(transcript_res, Exception):
                errors.append(f"transcript: {str(transcript_res)}")
            if isinstance(vision_res, Exception):
                errors.append(f"vision: {str(vision_res)}")
            timings.transcript_ms = int((time.time() - t0) * 1000)

            # Phase 2: Claim extraction
            t1 = time.time()
            context = {
                "transcript": transcript or "",
                "ocr_text": ocr_text or "",
                "title": metadata.get("title", ""),
                "description": metadata.get("description", ""),
                "channel": metadata.get("channel", ""),
            }
            claims_res = await self.claims.extract(**context)
            if claims_res.error:
                errors.append(f"claims: {claims_res.error}")
            timings.extraction_ms = int((time.time() - t1) * 1000)

            # Phase 3: Classification
            t2 = time.time()
            if claims_res.claims:
                claim_texts = [c.claim for c in claims_res.claims]
                class_res = await self.classifier.classify(claim_texts)
                for i, claim in enumerate(claims_res.claims):
                    if i < len(class_res.classifications):
                        claim.category = class_res.classifications[i].category
                        claim.classifier_confidence = class_res.classifications[i].confidence
                    else:
                        claim.category = "general"
            timings.classification_ms = int((time.time() - t2) * 1000)

            # Phase 4: Reasoning
            t3 = time.time()
            full_claims_text = " | ".join(c.claim for c in claims_res.claims) if claims_res.claims else (metadata.get("title", "") or transcript[:200] if transcript else video_id)

            evidence_docs = []
            if claims_res.claims:
                reason_res = await self.reasoning.analyze(
                    claim=claims_res.claims[0].claim,
                    claim_category=claims_res.claims[0].category,
                    transcript=transcript or "",
                    ocr_text=ocr_text or "",
                    evidence=[d.get("content", "") for d in evidence_docs]
                )
            else:
                reason_res = await self.reasoning.analyze(
                    claim=full_claims_text,
                    transcript=transcript or "",
                    ocr_text=ocr_text or "",
                    evidence=[]
                )
            timings.reasoning_ms = int((time.time() - t3) * 1000)

            # Phase 5: Trust score
            trust = self.trust.calculate(
                verdict=reason_res.verdict,
                llm_confidence=reason_res.confidence,
                evidence_sources=[d.get("metadata", {}) for d in evidence_docs],
                evidence_count=len(evidence_docs)
            )

            timings.total_ms = timings.transcript_ms + timings.extraction_ms + timings.classification_ms + timings.reasoning_ms

            result_dict = {
                "video_id": video_id,
                "analysis_id": analysis_id,
                "claim": reason_res.claim[:200],
                "verdict": reason_res.verdict,
                "confidence": trust.score,
                "trust_label": trust.label,
                "explanation": reason_res.explanation,
                "risk_level": reason_res.risk_level,
                "key_factors": reason_res.key_factors,
                "sources": reason_res.sources,
                "transcript_source": transcript_source,
                "transcript_used": transcript_source is not None,
                "ocr_used": ocr_used,
                "claims_list": [c.model_dump() for c in claims_res.claims],
                "video_summary": claims_res.video_summary,
                "processing_time_ms": timings.total_ms,
            }

        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            errors.append(f"pipeline: {str(e)}")
            result_dict = None

        status = "completed" if result_dict else "failed"
        return PipelineResult(
            analysis_id=analysis_id,
            video_id=video_id,
            status=status,
            result=result_dict,
            timings=timings,
            errors=errors
        )

    async def _extract_vision(self, video_id: str, claim: str) -> dict:
        try:
            from app.mcp.tools.vision import VisionTool
            tool = VisionTool()
            return await tool.execute(video_id=video_id, claim_text=claim)
        except Exception as e:
            logger.error(f"Vision extraction failed: {e}")
            return {"ocr_text": None, "used": False}
