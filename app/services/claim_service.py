import logging
from typing import Optional
from app.config import settings
from app.llm.client import call_llm, parse_json_response
from app.llm.prompt_loader import format_prompt
from app.schemas.pipeline_models import ClaimExtractionResult, Claim

logger = logging.getLogger("clearlens.services.claims")


class ClaimService:
    async def extract(self, transcript: str = "", ocr_text: str = "", title: str = "", description: str = "", channel: str = "", model_override: Optional[str] = None) -> ClaimExtractionResult:
        if not transcript and not ocr_text and not title:
            return ClaimExtractionResult(error="no content to analyze")
        if not settings.openrouter_api_key and not settings.openai_api_key:
            return ClaimExtractionResult(error="LLM API key not configured")

        parts = []
        if title:
            parts.append(f"TITLE: {title}")
        if description:
            parts.append(f"DESCRIPTION: {description}")
        if channel:
            parts.append(f"CHANNEL: {channel}")
        if transcript:
            parts.append(f"TRANSCRIPT:\n{transcript[:3000]}")
        if ocr_text:
            parts.append(f"OCR TEXT FROM VIDEO:\n{ocr_text[:1500]}")

        prompt = format_prompt("claim_extraction", context="\n\n".join(parts))
        content = await call_llm(prompt, max_tokens=2000, temperature=0.1, model_override=model_override)
        if content:
            parsed = parse_json_response(content)
            if parsed:
                claims = [Claim(**c) for c in parsed.get("claims", [])]
                return ClaimExtractionResult(claims=claims, video_summary=parsed.get("video_summary", ""))
        return ClaimExtractionResult(error="LLM call failed")
