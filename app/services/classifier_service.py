import logging
from typing import Optional
from app.config import settings
from app.llm.client import call_llm, parse_json_response
from app.llm.prompt_loader import format_prompt
from app.schemas.pipeline_models import ClassificationResult, ClassificationItem

logger = logging.getLogger("clearlens.services.classifier")


class ClassifierService:
    async def classify(self, claims: list[str], model_override: Optional[str] = None) -> ClassificationResult:
        if not claims:
            return ClassificationResult()
        if not settings.openrouter_api_key and not settings.openai_api_key:
            return ClassificationResult(
                classifications=[ClassificationItem(claim_index=i, category="general", confidence=0.0) for i in range(len(claims))]
            )

        items = "\n".join(f"{i+1}. {c}" for i, c in enumerate(claims))
        prompt = format_prompt("classification", items=items)
        content = await call_llm(prompt, max_tokens=1000, temperature=0.1, model_override=model_override)
        if content:
            parsed = parse_json_response(content)
            if parsed and "classifications" in parsed:
                items = [ClassificationItem(**c) for c in parsed["classifications"]]
                return ClassificationResult(classifications=items)
        return ClassificationResult(
            classifications=[ClassificationItem(claim_index=i, category="general", confidence=0.5) for i in range(len(claims))]
        )
