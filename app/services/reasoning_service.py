import logging
from typing import Optional
from app.config import settings
from app.llm.client import call_llm, parse_json_response
from app.llm.prompt_loader import format_prompt
from app.schemas.pipeline_models import ReasoningResult

logger = logging.getLogger("clearlens.services.reasoning")

FALLBACK_EXPLANATION = "Insufficient verifiable evidence was available to confidently determine the accuracy of this claim. Additional trusted sources are required."
FALLBACK_FACTORS = ["Limited supporting evidence", "Automatic fallback explanation"]


class ReasoningService:
    async def analyze(self, claim: str, claim_category: str = "", transcript: str = "", ocr_text: str = "", evidence: list[str] = None, model_override: Optional[str] = None, video_summary: str = "", strict: bool = False) -> Optional[ReasoningResult]:
        if not settings.openrouter_api_key and not settings.openai_api_key:
            if strict:
                return None
            return ReasoningResult(claim=claim[:200], explanation=FALLBACK_EXPLANATION, key_factors=FALLBACK_FACTORS.copy())

        evidence = evidence or []
        ctx_parts = []
        if transcript:
            ctx_parts.append(f"TRANSCRIPT:\n{transcript[:2000]}")
        if ocr_text:
            ctx_parts.append(f"OCR TEXT FROM VIDEO:\n{ocr_text[:1000]}")
        if video_summary:
            ctx_parts.append(f"VIDEO SUMMARY:\n{video_summary[:800]}")
        ctx_parts.append(f"CLAIM TO VERIFY:\n{claim}")
        if claim_category:
            ctx_parts.append(f"CLAIM CATEGORY: {claim_category}")
        if evidence:
            ctx_parts.append("EVIDENCE FROM TRUSTED SOURCES:")
            for i, doc in enumerate(evidence[:5], 1):
                ctx_parts.append(f"{i}. {doc[:1500]}")

        prompt = format_prompt("reasoning", context="\n\n".join(ctx_parts))

        for attempt in range(2):
            content = await call_llm(prompt, max_tokens=1200, temperature=0.1, model_override=model_override)
            if content:
                parsed = parse_json_response(content)
                if parsed:
                    validated = self._validate(parsed)
                    if validated:
                        return validated
                    logger.warning(f"LLM response failed validation (attempt {attempt + 1}), retrying...")
            else:
                logger.warning(f"LLM returned empty content (attempt {attempt + 1}), retrying...")

        return None if strict else self._fallback(claim[:200])

    def _validate(self, parsed: dict) -> ReasoningResult | None:
        verdict = parsed.get("verdict", "")
        confidence = parsed.get("confidence")
        explanation = parsed.get("explanation", "")
        key_factors = parsed.get("key_factors", [])

        if verdict not in ("true", "false", "misleading", "unverifiable"):
            return None
        if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
            return None
        if not explanation or len(str(explanation).strip()) < 30:
            return None
        if not isinstance(key_factors, list) or len(key_factors) < 2:
            return None

        sources = []
        raw_sources = parsed.get("sources", [])
        if isinstance(raw_sources, list):
            for s in raw_sources:
                if isinstance(s, dict) and s.get("url"):
                    sources.append({"title": str(s.get("title", "")), "url": str(s.get("url"))})
                elif isinstance(s, str) and s.strip():
                    sources.append({"title": s.strip(), "url": ""})
        parsed["sources"] = sources

        return ReasoningResult(**parsed)

    def _fallback(self, claim: str) -> ReasoningResult:
        return ReasoningResult(
            claim=claim,
            verdict="unverifiable",
            confidence=0.0,
            risk_level="medium",
            explanation=FALLBACK_EXPLANATION,
            key_factors=FALLBACK_FACTORS.copy(),
            sources=[]
        )