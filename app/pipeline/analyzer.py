import logging
from typing import Optional
from app.pipeline.orchestrator import PipelineOrchestrator
from app.data.database import Database
from app.data.models import AnalysisResult
from app.data.repositories.analysis_repository import AnalysisRepository

logger = logging.getLogger("clearlens.analyzer")


class Analyzer:
    def __init__(self, db: Database):
        self._repo = AnalysisRepository(db)
        self._orchestrator = PipelineOrchestrator()

    async def analyze(self, video_id: str, metadata: dict, user_id: str) -> dict:
        cached = self._repo.get_cached(video_id)
        if cached:
            return cached

        pipeline_res = await self._orchestrator.run(video_id, metadata)
        result_dict = pipeline_res.result

        if not result_dict or pipeline_res.status == "failed":
            return {
                "video_id": video_id,
                "claim": metadata.get("title", "")[:200],
                "verdict": "unverifiable",
                "confidence": 0.0,
                "trust_label": "very low",
                "explanation": "Pipeline processing failed.",
                "sources": [],
                "transcript_used": False,
                "ocr_used": False,
                "claims_list": [],
                "video_summary": "",
                "processing_time_ms": pipeline_res.timings.total_ms,
                "errors": pipeline_res.errors,
            }

        result = AnalysisResult(
            video_id=video_id,
            user_id=user_id,
            claim=result_dict.get("claim", ""),
            verdict=result_dict.get("verdict", "unverifiable"),
            confidence=result_dict.get("confidence", 0.0),
            explanation=result_dict.get("explanation", ""),
            sources=result_dict.get("sources", []),
            transcript_used=result_dict.get("transcript_used", False),
            ocr_used=result_dict.get("ocr_used", False),
            processing_time_ms=result_dict.get("processing_time_ms", 0)
        )

        result_dict["trust_label"] = result_dict.get("trust_label", "very low")
        self._repo.set_cache(video_id, result_dict)
        self._repo.save_history(result)

        return result_dict
