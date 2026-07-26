from typing import Optional
from app.mcp.tools.base import Tool, ToolSpec
from app.config import settings


class TranscriptTool(Tool):
    spec = ToolSpec(
        name="extract_transcript",
        description="Extract transcript from a YouTube video. Returns text or None if unavailable.",
        input_schema={
            "type": "object",
            "properties": {
                "video_id": {"type": "string", "description": "YouTube video ID"}
            },
            "required": ["video_id"]
        }
    )

    async def execute(self, video_id: str) -> dict:
        text = await self._fetch_transcript(video_id)
        if text:
            return {"transcript": text, "source": "youtube_api"}
        text = await self._whisper_transcribe(video_id)
        if text:
            return {"transcript": text, "source": "whisper"}
        return {"transcript": None, "source": None}

    async def _fetch_transcript(self, video_id: str) -> Optional[str]:
        try:
            import httpx
            url = f"https://youtubetranscript.com/api?vid={video_id}"
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if "text" in data:
                        return data["text"]
                    if isinstance(data, list):
                        return " ".join(seg.get("text", "") for seg in data)
        except Exception:
            pass
        return None

    async def _whisper_transcribe(self, video_id: str) -> Optional[str]:
        if not settings.openai_api_key:
            return None
        try:
            import httpx
            audio_url = f"https://www.youtube.com/watch?v={video_id}"
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                    data={"model": "whisper-1", "url": audio_url},
                    timeout=30
                )
                if resp.status_code == 200:
                    return resp.json().get("text")
        except Exception:
            pass
        return None
