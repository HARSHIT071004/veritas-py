import logging
from app.config import settings
from app.llm.client import call_llm, parse_json_response
from app.llm.prompt_loader import format_prompt
from app.schemas.pipeline_models import ReasoningResult

logger = logging.getLogger("clearlens.services.reasoning")


class ReasoningService:
    async def analyze(self, claim: str, claim_category: str = "", transcript: str = "", ocr_text: str = "", evidence: list[str] = None) -> ReasoningResult:
        if not settings.openrouter_api_key and not settings.openai_api_key:
            return ReasoningResult(claim=claim[:200])

        evidence = evidence or []
        ctx_parts = []
        if transcript:
            ctx_parts.append(f"TRANSCRIPT:\n{transcript[:2000]}")
        if ocr_text:
            ctx_parts.append(f"OCR TEXT FROM VIDEO:\n{ocr_text[:1000]}")
        ctx_parts.append(f"CLAIM TO VERIFY:\n{claim}")
        if claim_category:
            ctx_parts.append(f"CLAIM CATEGORY: {claim_category}")
        if evidence:
            ctx_parts.append("EVIDENCE FROM TRUSTED SOURCES:")
            for i, doc in enumerate(evidence[:5], 1):
                ctx_parts.append(f"{i}. {doc[:1500]}")

        prompt = format_prompt("reasoning", context="\n\n".join(ctx_parts))
        content = await call_llm(prompt, max_tokens=1200, temperature=0.1)
        if content:
            parsed = parse_json_response(content)
            if parsed:
                return ReasoningResult(**parsed)
        return ReasoningResult(claim=claim[:200])
