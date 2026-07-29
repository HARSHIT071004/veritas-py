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
from app.llm.client import call_llm, parse_json_response
from app.llm.prompt_loader import format_prompt
from app.schemas.pipeline_models import PipelineResult, PipelineTimings, Claim, ClaimExtractionResult, ReasoningResult

logger = logging.getLogger("clearlens.orchestrator")


FAST_MODEL = "llama-3.1-8b-instant"
BALANCED_MODEL = None
ACCURATE_MODEL = None


class PipelineOrchestrator:
    def __init__(self):
        self.transcript = TranscriptService()
        self.claims = ClaimService()
        self.classifier = ClassifierService()
        self.reasoning = ReasoningService()
        self.trust = TrustService()

    async def run(self, video_id: str, metadata: dict, mode: str = "balanced") -> PipelineResult:
        analysis_id = uuid.uuid4().hex[:12]
        timings = PipelineTimings()
        internal_timings = {}
        errors = []
        result_dict = None

        t_start = time.time()

        try:
            t_meta = time.time()
            meta = await self.transcript.get_metadata(video_id)
            internal_timings["metadata_ms"] = int((time.time() - t_meta) * 1000)

            if not metadata.get("title") and meta.get("title"):
                metadata["title"] = meta["title"]
            if not metadata.get("channel") and meta.get("channel"):
                metadata["channel"] = meta["channel"]

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

            combined_res = None
            if transcript:
                combined_res = await self._run_combined_analysis(transcript, metadata, mode=mode)

            if combined_res:
                claims_res = combined_res["claims_res"]
                reason_res = combined_res["reason_res"]
                timings.extraction_ms = combined_res["extraction_ms"]
                timings.classification_ms = combined_res["classification_ms"]
                timings.reasoning_ms = combined_res["reasoning_ms"]
            else:
                t1 = time.time()
                context = {
                    "transcript": transcript or "",
                    "ocr_text": ocr_text or "",
                    "title": metadata.get("title", ""),
                    "description": metadata.get("description", ""),
                    "channel": metadata.get("channel", ""),
                }
                model_override = FAST_MODEL if mode == "fast" else ACCURATE_MODEL
                if mode == "accurate":
                    claims_res = await self.claims.extract(**context, model_override=model_override)
                else:
                    claims_res = await self.claims.extract(**context)
                if claims_res.error:
                    errors.append(f"claims: {claims_res.error}")
                timings.extraction_ms = int((time.time() - t1) * 1000)

                t2 = time.time()
                if claims_res.claims:
                    claim_texts = [c.claim for c in claims_res.claims]
                    if mode == "accurate":
                        class_res = await self.classifier.classify(claim_texts, model_override=model_override)
                    else:
                        class_res = await self.classifier.classify(claim_texts)
                    for i, claim in enumerate(claims_res.claims):
                        if i < len(class_res.classifications):
                            claim.category = class_res.classifications[i].category
                            claim.classifier_confidence = class_res.classifications[i].confidence
                        else:
                            claim.category = "general"
                timings.classification_ms = int((time.time() - t2) * 1000)

                t3 = time.time()
                full_claims_text = " | ".join(c.claim for c in claims_res.claims) if claims_res.claims else (metadata.get("title", "") or transcript[:200] if transcript else video_id)
                evidence_docs = []
                if claims_res.claims:
                    if mode == "accurate":
                        reason_res = await self.reasoning.analyze(
                            claim=claims_res.claims[0].claim,
                            claim_category=claims_res.claims[0].category,
                            transcript=transcript or "",
                            ocr_text=ocr_text or "",
                            evidence=[d.get("content", "") for d in evidence_docs],
                            model_override=model_override
                        )
                    else:
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

            evidence_docs = []
            trust = self.trust.calculate(
                verdict=reason_res.verdict,
                llm_confidence=reason_res.confidence,
                evidence_sources=[d.get("metadata", {}) for d in evidence_docs],
                evidence_count=len(evidence_docs)
            )

            timings.total_ms = int((time.time() - t_start) * 1000)

            total_llm = timings.extraction_ms + timings.classification_ms + timings.reasoning_ms
            pre_llm = timings.total_ms - total_llm
            logger.info(
                f"Pipeline finished",
                extra={
                    "video_id": video_id,
                    "analysis_id": analysis_id,
                    "mode": mode,
                    "metadata_ms": internal_timings.get("metadata_ms", 0),
                    "transcript_ms": timings.transcript_ms,
                    "extraction_ms": timings.extraction_ms,
                    "classification_ms": timings.classification_ms,
                    "reasoning_ms": timings.reasoning_ms,
                    "pre_llm_ms": pre_llm,
                    "total_ms": timings.total_ms,
                    "transcript_source": transcript_source,
                    "combined_path": combined_res is not None,
                }
            )

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

    async def _run_combined_analysis(self, transcript: str, metadata: dict, mode: str = "balanced") -> Optional[dict]:
        t_start = time.time()
        try:
            model_override = FAST_MODEL if mode == "fast" else (ACCURATE_MODEL if mode == "accurate" else None)
            prompt = format_prompt("combined_analysis", transcript=transcript[:4000], title=metadata.get("title", "")[:200], channel=metadata.get("channel", "")[:100])
            content = await call_llm(prompt, max_tokens=3000, temperature=0.1, model_override=model_override)
            if not content:
                return None
            parsed = parse_json_response(content)
            if not parsed or "claims" not in parsed:
                return None

            claims_data = parsed["claims"]
            if not claims_data:
                return None

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
            logger.warning(f"Combined analysis failed, falling back to sequential: {e}")
            return None

    async def _extract_vision(self, video_id: str, claim: str) -> dict:
        try:
            from app.mcp.tools.vision import VisionTool
            tool = VisionTool()
            return await tool.execute(video_id=video_id, claim_text=claim)
        except Exception as e:
            logger.error(f"Vision extraction failed: {e}")
            return {"ocr_text": None, "used": False}