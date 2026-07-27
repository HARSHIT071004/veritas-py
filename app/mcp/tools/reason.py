from app.mcp.tools.base import Tool, ToolSpec
from app.services.reasoning_service import ReasoningService


class ReasonTool(Tool):
    spec = ToolSpec(
        name="reason_verdict",
        description="Analyze a claim against evidence and return a verdict with explanation.",
        input_schema={
            "type": "object",
            "properties": {
                "claim": {"type": "string"},
                "claim_category": {"type": "string"},
                "transcript": {"type": "string"},
                "ocr_text": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["claim"]
        }
    )

    def __init__(self):
        self._service = ReasoningService()

    async def execute(self, claim: str, claim_category: str = "", transcript: str = "", ocr_text: str = "", evidence: list = None) -> dict:
        result = await self._service.analyze(
            claim=claim, claim_category=claim_category,
            transcript=transcript, ocr_text=ocr_text,
            evidence=evidence or []
        )
        return result.model_dump()
