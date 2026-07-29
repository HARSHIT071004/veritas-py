from app.mcp.tools.base import Tool, ToolSpec
from app.services.classifier_service import ClassifierService


class ClassifierTool(Tool):
    spec = ToolSpec(
        name="classify_claim",
        description="Classify claims into categories (health, political, scientific, etc.) with confidence scores.",
        input_schema={
            "type": "object",
            "properties": {
                "claims": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of claim strings to classify"
                }
            },
            "required": ["claims"]
        }
    )

    def __init__(self):
        self._service = ClassifierService()

    async def execute(self, claims: list) -> dict:
        result = await self._service.classify(claims)
        return {"classifications": [c.model_dump() for c in result.classifications]}
