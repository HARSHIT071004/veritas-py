import json
from app.mcp.tools.base import Tool, ToolSpec
from app.config import settings
from app.llm.client import call_llm, parse_json_response


class ReasonTool(Tool):
    spec = ToolSpec(
        name="reason_verdict",
        description="Analyze a claim against evidence and return a verdict with explanation.",
        input_schema={
            "type": "object",
            "properties": {
                "claim": {"type": "string"},
                "transcript": {"type": "string"},
                "ocr_text": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["claim"]
        }
    )

    async def execute(self, claim: str, transcript: str = "", ocr_text: str = "", evidence: list = None) -> dict:
        if not settings.openrouter_api_key and not settings.openai_api_key:
            return self._fallback_verdict(claim)
        evidence = evidence or []
        prompt = self._build_prompt(claim, transcript, ocr_text, evidence)
        content = await call_llm(prompt, max_tokens=1000, temperature=0.1)
        if content:
            parsed = parse_json_response(content)
            if parsed:
                return parsed
        return self._fallback_verdict(claim)

    def _build_prompt(self, claim: str, transcript: str, ocr_text: str, evidence: list[str]) -> str:
        ctx_parts = []
        if transcript:
            ctx_parts.append(f"TRANSCRIPT:\n{transcript[:2000]}")
        if ocr_text:
            ctx_parts.append(f"OCR TEXT FROM VIDEO:\n{ocr_text[:1000]}")
        ctx_parts.append(f"CLAIM TO VERIFY:\n{claim}")
        if evidence:
            ctx_parts.append("EVIDENCE FROM TRUSTED SOURCES:")
            for i, doc in enumerate(evidence[:5], 1):
                ctx_parts.append(f"{i}. {doc[:1500]}")
        context = "\n\n".join(ctx_parts)

        return f"""You are a misinformation detection assistant. Analyze the claim against the provided evidence.

{context}

Respond with JSON only:
{{
  "claim": "the claim being evaluated",
  "verdict": "true | false | misleading | unverifiable",
  "confidence": 0.0-1.0,
  "explanation": "brief explanation of reasoning",
  "sources": ["source1", "source2"]
}}

Rules:
- Return "false" ONLY if evidence directly contradicts the claim
- Return "unverifiable" if evidence is insufficient
- Never guess. Lack of evidence is not proof of falsehood.
- Confidence must reflect how strongly evidence supports the verdict."""

    def _fallback_verdict(self, claim: str) -> dict:
        return {
            "claim": claim[:200],
            "verdict": "unverifiable",
            "confidence": 0.0,
            "explanation": "Analysis unavailable. LLM API key not configured or request failed.",
            "sources": []
        }
