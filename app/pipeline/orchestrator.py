import time
import asyncio
import logging
from typing import Optional
from app.pipeline.stage import StageContext
from app.pipeline.cache import MultiLevelCache
from app.schemas.pipeline_models import PipelineResult, PipelineTimings

logger = logging.getLogger("clearlens.orchestrator")

FAST_MODEL = "llama-3.1-8b-instant"
BALANCED_MODEL = None
ACCURATE_MODEL = None


class PipelineOrchestrator:
    def __init__(self, cache: MultiLevelCache = None, rag_engine=None, db=None):
        self._cache = cache
        self._rag_engine = rag_engine
        self._db = db
        self._stages: dict[str, object] = {}
        self._register_stages()

    def _register_stages(self):
        from app.pipeline.stages.video_detection import VideoDetectionStage
        from app.pipeline.stages.metadata import MetadataStage
        from app.pipeline.stages.transcript import TranscriptStage
        from app.pipeline.stages.visual_analysis import VisualAnalysisStage
        from app.pipeline.stages.context_builder import ContextBuilderStage
        from app.pipeline.stages.claim_analysis import ClaimAnalysisStage
        from app.pipeline.stages.evidence_retrieval import EvidenceRetrievalStage
        from app.pipeline.stages.trust_score import TrustScoreStage
        from app.pipeline.stages.response_builder import ResponseBuilderStage

        for cls in [
            VideoDetectionStage,
            MetadataStage,
            TranscriptStage,
            VisualAnalysisStage,
            ContextBuilderStage,
            ClaimAnalysisStage,
            EvidenceRetrievalStage,
            TrustScoreStage,
            ResponseBuilderStage,
        ]:
            stage = cls()
            self._stages[stage.name] = stage

    def _resolve_execution_order(self) -> list[list[str]]:
        stages = list(self._stages.keys())
        deps = {name: list(self._stages[name].dependencies) for name in stages}
        executed = set()
        levels = []

        while len(executed) < len(stages):
            level = []
            for name in stages:
                if name in executed:
                    continue
                if all(d in executed for d in deps[name]):
                    level.append(name)
            if not level:
                raise RuntimeError(f"circular dependency detected among: {set(stages) - executed}")
            executed.update(level)
            levels.append(level)

        return levels

    async def run(self, video_id: str, metadata: dict, mode: str = "balanced", user_id: str = "", prefetched: bool = False) -> PipelineResult:
        ctx = StageContext(
            video_id=video_id,
            metadata=dict(metadata),
            mode=mode,
            user_id=user_id,
            prefetched=prefetched,
            cache=self._cache,
            rag_engine=self._rag_engine,
            db=self._db,
        )

        timings = PipelineTimings()
        internal_timings = {}
        errors = []
        results: dict[str, dict] = {}
        t_start = time.time()

        try:
            levels = self._resolve_execution_order()
            logger.info(f"Pipeline execution order: {levels}")

            for level in levels:
                t_level = time.time()
                tasks = {}
                for name in level:
                    stage = self._stages[name]
                    stage_inputs = {dep: results.get(dep, {}) for dep in stage.dependencies}
                    tasks[name] = stage.run(ctx, stage_inputs)

                level_results = await asyncio.gather(*tasks.values(), return_exceptions=True)
                level_names = list(tasks.keys())

                for i, name in enumerate(level_names):
                    res = level_results[i]
                    if isinstance(res, Exception):
                        errors.append(f"{name}: {str(res)}")
                        results[name] = {}
                    elif not res.success:
                        errors.append(f"{name}: {res.error}")
                        results[name] = res.data or {}
                        internal_timings[f"{name}_ms"] = res.timing_ms
                    else:
                        results[name] = res.data
                        internal_timings[f"{name}_ms"] = res.timing_ms

                internal_timings[f"level_{len(levels) - levels.index(level)}_ms"] = int((time.time() - t_level) * 1000)

            final = results.get("response_builder", {})
            timings.total_ms = int((time.time() - t_start) * 1000)
            timings.transcript_ms = internal_timings.get("transcript_ms", 0)
            timings.extraction_ms = internal_timings.get("claim_analysis_ms", 0)
            timings.classification_ms = internal_timings.get("claim_analysis_ms", 0)
            timings.reasoning_ms = internal_timings.get("trust_score_ms", 0)

            logger.info(
                f"Pipeline finished",
                extra={
                    "video_id": video_id,
                    "mode": mode,
                    "timings": internal_timings,
                    "total_ms": timings.total_ms,
                    "errors": errors[:3],
                }
            )

            result_dict = {
                "video_id": video_id,
                "claim": final.get("claim", ""),
                "verdict": final.get("verdict", "unverifiable"),
                "confidence": final.get("confidence", 0.0),
                "trust_label": final.get("trust_label", "very low"),
                "explanation": final.get("explanation", ""),
                "risk_level": final.get("risk_level", "medium"),
                "key_factors": final.get("key_factors", []),
                "sources": final.get("sources", []),
                "transcript_source": final.get("transcript_source"),
                "transcript_used": final.get("transcript_used", False),
                "ocr_used": final.get("ocr_used", False),
                "claims_list": final.get("claims_list", []),
                "video_summary": final.get("video_summary", ""),
                "processing_time_ms": timings.total_ms,
            }

            return PipelineResult(
                analysis_id=video_id[:12],
                video_id=video_id,
                status="completed",
                result=result_dict,
                timings=timings,
                errors=errors,
            )

        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            errors.append(f"pipeline: {str(e)}")
            return PipelineResult(
                analysis_id=video_id[:12],
                video_id=video_id,
                status="failed",
                result=None,
                timings=timings,
                errors=errors,
            )
