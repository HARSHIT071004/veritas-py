from app.pipeline.stage import PipelineStage, StageContext, StageResult


class ContextBuilderStage(PipelineStage):
    name = "context_builder"
    dependencies = ["metadata", "transcript", "visual_analysis"]

    async def execute(self, ctx: StageContext, inputs: dict) -> StageResult:
        metadata = inputs.get("metadata", {})
        transcript = inputs.get("transcript", {})
        visual = inputs.get("visual_analysis", {})

        context = {
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "channel": metadata.get("channel", ""),
            "hashtags": metadata.get("hashtags", []),
            "thumbnail": metadata.get("thumbnail", ""),
            "transcript": transcript.get("text", "") or "",
            "transcript_source": transcript.get("source"),
            "transcript_available": transcript.get("available", False),
            "ocr_text": visual.get("ocr_text", "") or "",
            "ocr_used": visual.get("used", False),
        }

        return StageResult(data=context)
