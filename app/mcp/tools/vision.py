import base64
import logging
from typing import Optional
from app.mcp.tools.base import Tool, ToolSpec
from app.config import settings

logger = logging.getLogger("clearlens")


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
        frames = await self._extract_frames(video_id)
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

    async def _extract_frames(self, video_id: str) -> Optional[list[bytes]]:
        frames = []

        # Try OpenCV-based frames from downloaded video first
        if settings.opencv_frames_enabled:
            try:
                from app.vision.frames import extract_frames
                cv_frames = await extract_frames(video_id)
                if cv_frames:
                    frames.extend(cv_frames)
            except Exception:
                pass

        # Fall back to YouTube thumbnails
        if not frames:
            frames = await self._fetch_thumbnails(video_id)

        return frames if frames else None

    async def _fetch_thumbnails(self, video_id: str) -> list[bytes]:
        import httpx
        import asyncio

        frames = []
        async with httpx.AsyncClient() as client:
            urls = [
                f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                f"https://img.youtube.com/vi/{video_id}/sddefault.jpg",
                f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
            ]
            tasks = [client.get(url, timeout=10) for url in urls]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            for resp in responses:
                if isinstance(resp, Exception) or resp.status_code != 200:
                    continue
                frames.append(resp.content)
                if len(frames) >= 3:
                    break
        return frames

    async def _ocr_frames(self, frames: list[bytes]) -> str:
        extracted = []
        for raw in frames:
            text = await self._ocr_single(raw)
            if text:
                extracted.append(text)
        return "\n---\n".join(extracted)

    async def _ocr_single(self, image_bytes: bytes) -> Optional[str]:
        engines = []

        if settings.paddle_ocr_enabled:
            engines.append(("paddle-vl", self._ocr_paddle_vl))
            engines.append(("paddle", self._ocr_paddle))
        if settings.easy_ocr_enabled:
            engines.append(("easyocr", self._ocr_easy))
        engines.append(("gemini", self._ocr_gemini))

        for name, method in engines:
            try:
                text = await method(image_bytes)
                if text:
                    return text
            except Exception:
                pass
        return None

    async def _ocr_paddle_vl(self, image_bytes: bytes) -> Optional[str]:
        from app.vision.paddle_ocr_vl import ocr_image, is_available
        if not is_available():
            return None
        return await ocr_image(image_bytes)

    async def _ocr_paddle(self, image_bytes: bytes) -> Optional[str]:
        from app.vision.paddle_ocr import ocr_image, is_available
        if not is_available():
            return None
        return await ocr_image(image_bytes)

    async def _ocr_easy(self, image_bytes: bytes) -> Optional[str]:
        from app.vision.easy_ocr import ocr_image, is_available
        if not is_available():
            return None
        return await ocr_image(image_bytes)

    async def _ocr_gemini(self, image_bytes: bytes) -> Optional[str]:
        if not settings.gemini_api_key:
            return None
        try:
            import httpx
            b64 = base64.b64encode(image_bytes).decode()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.gemini_api_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": "Extract all visible text from this image. Include headlines, captions, overlays, meme text, and any text in screenshots. Return only the extracted text, no commentary."},
                        {"inline_data": {"mime_type": "image/jpeg", "data": b64}}
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
