from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.services.transcript_service import TranscriptService


class MetadataStage(PipelineStage):
    name = "metadata"
    dependencies = ["video_detection"]
    _service = TranscriptService()

    async def execute(self, ctx: StageContext, inputs: dict) -> StageResult:
        video_id = ctx.video_id
        meta = await self._service.get_metadata(video_id)

        merged = dict(ctx.metadata)
        if not merged.get("title") and meta.get("title"):
            merged["title"] = meta["title"]
        if not merged.get("channel") and meta.get("channel"):
            merged["channel"] = meta["channel"]
        if meta.get("thumbnail"):
            merged["thumbnail"] = meta["thumbnail"]

        return StageResult(data=merged)
