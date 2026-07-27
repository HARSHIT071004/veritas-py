import json
from app.mcp.tools.base import Tool, ToolSpec
from app.config import settings
from app.llm.client import call_llm, parse_json_response


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

    async def execute(self, transcript: str = "", ocr_text: str = "", title: str = "", description: str = "", channel: str = "") -> dict:
        if not transcript and not ocr_text and not title:
            return {"claims": [], "video_summary": "", "error": "no content to analyze"}
        if not settings.openrouter_api_key and not settings.openai_api_key:
            return {"claims": [], "video_summary": "", "error": "LLM API key not configured"}
        prompt = self._build_prompt(transcript, ocr_text, title, description, channel)
        content = await call_llm(prompt, max_tokens=2000, temperature=0.1)
        if content:
            parsed = parse_json_response(content)
            if parsed:
                return parsed
        return {"claims": [], "video_summary": "", "error": "LLM call failed"}

    def _build_prompt(self, transcript: str, ocr_text: str, title: str, description: str, channel: str) -> str:
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

        context = "\n\n".join(parts)

        return f"""You are a claim extraction assistant. Analyze the video content below and extract ALL factual claims that could be verified or fact-checked.

{context}

For each claim, determine its category:
- health: medical claims, treatments, cures, vaccines, nutrition
- political: elections, policies, government actions
- scientific: research findings, studies, data claims
- financial: money, investments, economic claims
- conspiracy: conspiracy theories, hidden agendas
- general: other factual claims

Return ONLY valid JSON:
{{
  "video_summary": "one-line summary of the video",
  "claims": [
    {{
      "claim": "exact factual claim as stated",
      "category": "health|political|scientific|financial|conspiracy|general",
      "confidence": 0.0-1.0,
      "context": "surrounding context that clarifies the claim"
    }}
  ]
}}

Rules:
- Extract only factual claims (things that can be verified as true/false)
- Ignore opinions, jokes, rhetorical questions
- If no factual claims found, return empty claims array
- Be precise — quote the claim as closely as possible"""
