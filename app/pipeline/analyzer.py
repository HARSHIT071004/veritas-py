import asyncio
import logging
from typing import Optional
from app.pipeline.orchestrator import PipelineOrchestrator
from app.pipeline.cache import MultiLevelCache
from app.data.database import Database
from app.data.models import AnalysisResult
from app.data.repositories.analysis_repository import AnalysisRepository

logger = logging.getLogger("clearlens.analyzer")

_in_flight: dict[str, asyncio.Future] = {}


class Analyzer:
    def __init__(self, db: Database, cache: MultiLevelCache = None, rag_engine=None):
        self._repo = AnalysisRepository(db)
        self._orchestrator = PipelineOrchestrator(cache=cache, rag_engine=rag_engine, db=db)

    async def analyze(self, video_id: str, metadata: dict, user_id: str, mode: str = "balanced", prefetched: bool = False) -> dict:
        cached = self._repo.get_cached(video_id)
        if cached:
            return cached

        if video_id in _in_flight:
            logger.info(f"Dedup hit for {video_id}, waiting for in-flight analysis")
            return await _in_flight[video_id]

        loop = asyncio.get_event_loop()
        future = loop.create_future()
        _in_flight[video_id] = future
        try:
            result_dict = await self._run_pipeline(video_id, metadata, user_id, mode, prefetched)
            future.set_result(result_dict)
            return result_dict
        except Exception as e:
            if not future.done():
                future.set_exception(e)
            raise
        finally:
            _in_flight.pop(video_id, None)

    async def _run_pipeline(self, video_id: str, metadata: dict, user_id: str, mode: str, prefetched: bool) -> dict:
        pipeline_res = await self._orchestrator.run(video_id, metadata, mode=mode, user_id=user_id, prefetched=prefetched)
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
