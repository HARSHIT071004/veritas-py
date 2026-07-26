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
        return {"ocr_text": text, "used": True, "reason": "completed", "frames": len(frames)}

    def _needs_vision(self, claim: str) -> bool:
        triggers = [
            "this image", "this screenshot", "this photo", "this meme",
            "this post", "this graphic", "this chart", "this picture",
            "visual", "screenshot", "overlay", "caption shows",
            "text says", "screen shows", "graph shows"
        ]
        return any(t in claim.lower() for t in triggers)

    async def _extract_keyframes(self, video_id: str) -> Optional[list[str]]:
        frames = []
        import httpx
        import asyncio
        import base64

        async with httpx.AsyncClient() as client:
            thumbnail_urls = [
                f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                f"https://img.youtube.com/vi/{video_id}/sddefault.jpg",
                f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
            ]
            tasks = [client.get(url, timeout=10) for url in thumbnail_urls]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            for resp in responses:
                if isinstance(resp, Exception) or resp.status_code != 200:
                    continue
                b64 = base64.b64encode(resp.content).decode()
                frames.append(f"data:image/jpeg;base64,{b64}")
                if len(frames) >= 3:
                    break

        return frames if frames else None

    async def _ocr_frames(self, frames: list[str]) -> str:
        if not settings.gemini_api_key:
            return ""
        extracted = []
        for frame in frames:
            text = await self._gemini_ocr(frame)
            if text:
                extracted.append(text)
        return "\n---\n".join(extracted)

    async def _gemini_ocr(self, image_b64: str) -> Optional[str]:
        try:
            import httpx
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.gemini_api_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": "Extract all visible text from this image. Include headlines, captions, overlays, meme text, and any text in screenshots. Return only the extracted text, no commentary."},
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
