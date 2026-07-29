import re
from app.pipeline.stage import PipelineStage, StageContext, StageResult


VIDEO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{5,}$")


class VideoDetectionStage(PipelineStage):
    name = "video_detection"
    dependencies = []

    async def execute(self, ctx: StageContext, inputs: dict) -> StageResult:
        video_id = ctx.video_id
        url = inputs.get("url", "")

        if not video_id:
            if url:
                match = re.search(r"(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{5,})", url)
                if match:
                    video_id = match.group(1)
                else:
                    return StageResult(success=False, error="could not extract video_id from url")
            else:
                return StageResult(success=False, error="no video_id or url provided")

        if not VIDEO_ID_PATTERN.match(video_id):
            return StageResult(success=False, error=f"invalid video_id format: {video_id}")

        return StageResult(data={
            "video_id": video_id,
            "valid": True,
        })
