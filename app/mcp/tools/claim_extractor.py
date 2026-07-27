from app.mcp.tools.base import Tool, ToolSpec
from app.services.claim_service import ClaimService


class ClaimExtractorTool(Tool):
    spec = ToolSpec(
        name="extract_claims",
        description="Extract factual claims from video transcript, OCR text, and metadata. Returns structured JSON.",
        input_schema={
            "type": "object",
            "properties": {
                "transcript": {"type": "string"},
                "ocr_text": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "channel": {"type": "string"}
            },
            "required": ["transcript"]
        }
    )

    def __init__(self):
        self._service = ClaimService()

    async def execute(self, transcript: str = "", ocr_text: str = "", title: str = "", description: str = "", channel: str = "") -> dict:
        result = await self._service.extract(transcript=transcript, ocr_text=ocr_text, title=title, description=description, channel=channel)
        return {"claims": [c.model_dump() for c in result.claims], "video_summary": result.video_summary, "error": result.error}
