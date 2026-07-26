from typing import Optional
from app.mcp.tools.base import Tool, ToolSpec
from app.config import settings


class VisionTool(Tool):
    spec = ToolSpec(
        name="extract_vision_text",
        description="Extract text from video keyframes using OCR. Returns text overlay, captions, headlines.",
        input_schema={
            "type": "object",
            "properties": {
                "video_id": {"type": "string", "description": "YouTube video ID"},
                "claim_text": {"type": "string", "description": "Claim to check if vision is needed"}
            },
            "required": ["video_id", "claim_text"]
        }
    )

    async def execute(self, video_id: str, claim_text: str) -> dict:
        if not self._needs_vision(claim_text):
            return {"ocr_text": None, "used": False, "reason": "skipped"}
        frames = await self._extract_keyframes(video_id)
        if not frames:
            return {"ocr_text": None, "used": True, "reason": "no_frames"}
        text = await self._ocr_frames(frames)
        return {"ocr_text": text, "used": True, "reason": "completed"}

    def _needs_vision(self, claim: str) -> bool:
        triggers = [
            "this image", "this screenshot", "this photo", "this meme",
            "this post", "this graphic", "this chart", "this picture",
            "visual", "screenshot", "overlay", "caption shows"
        ]
        return any(t in claim.lower() for t in triggers)

    async def _extract_keyframes(self, video_id: str) -> Optional[list[str]]:
        try:
            import httpx
            url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10)
                if resp.status_code == 200:
                    import base64
                    b64 = base64.b64encode(resp.content).decode()
                    return [f"data:image/jpeg;base64,{b64}"]
        except Exception:
            pass
        return None

    async def _ocr_frames(self, frames: list[str]) -> str:
        if not settings.gemini_api_key:
            return ""
        extracted = []
        for frame in frames:
            text = await self._gemini_ocr(frame)
            if text:
                extracted.append(text)
        return "\n".join(extracted)

    async def _gemini_ocr(self, image_b64: str) -> Optional[str]:
        try:
            import httpx
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.gemini_api_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": "Extract all visible text from this image. Include headlines, captions, overlays, and meme text. Return only the extracted text, no commentary."},
                        {"inline_data": {"mime_type": "image/jpeg", "data": image_b64.split(",")[-1]}}
                    ]
                }]
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=15)
                if resp.status_code == 200:
                    candidates = resp.json().get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        return " ".join(p.get("text", "") for p in parts)
        except Exception:
            pass
        return None
