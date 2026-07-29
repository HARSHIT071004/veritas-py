from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.services.transcript_service import TranscriptService


class TranscriptStage(PipelineStage):
    name = "transcript"
    dependencies = ["video_detection"]
    _service = TranscriptService()

    async def execute(self, ctx: StageContext, inputs: dict) -> StageResult:
        result = await self._service.extract(ctx.video_id)
        return StageResult(data={
            "text": result.text,
            "source": result.source,
            "language": result.language,
            "duration": result.duration,
            "available": result.text is not None,
        })
