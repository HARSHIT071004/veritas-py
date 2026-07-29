from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.mcp.tools.vision import VisionTool


class VisualAnalysisStage(PipelineStage):
    name = "visual_analysis"
    dependencies = ["video_detection"]
    _tool = VisionTool()

    async def execute(self, ctx: StageContext, inputs: dict) -> StageResult:
        claim_text = ctx.metadata.get("title", "")
        result = await self._tool.execute(video_id=ctx.video_id, claim_text=claim_text)
        return StageResult(data={
            "ocr_text": result.get("ocr_text"),
            "used": result.get("used", False),
            "reason": result.get("reason", ""),
            "frames": result.get("frames", 0),
        })
