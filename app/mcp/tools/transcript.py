from app.mcp.tools.base import Tool, ToolSpec
from app.services.transcript_service import TranscriptService


class TranscriptTool(Tool):
    spec = ToolSpec(
        name="extract_transcript",
        description="Extract transcript from a YouTube video. Returns structured text, language, duration, source.",
        input_schema={
            "type": "object",
            "properties": {
                "video_id": {"type": "string", "description": "YouTube video ID"}
            },
            "required": ["video_id"]
        }
    )

    def __init__(self):
        self._service = TranscriptService()

    async def execute(self, video_id: str) -> dict:
        result = await self._service.extract(video_id)
        return result.model_dump()
