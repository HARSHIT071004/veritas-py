import os
import tempfile
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
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://youtubetranscript.com/api?vid={video_id}",
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        return " ".join(seg.get("text", "") for seg in data)
                    if isinstance(data, dict) and "text" in data:
                        return data["text"]
        except Exception:
            pass
        return None

    async def _whisper_transcribe(self, video_id: str) -> Optional[str]:
        if not settings.openai_api_key:
            return None
        audio_path = None
        try:
            audio_path = await self._download_audio(video_id)
            if not audio_path:
                return None
            return await self._send_to_whisper(audio_path)
        except Exception:
            return None
        finally:
            if audio_path and os.path.exists(audio_path):
                try:
                    os.unlink(audio_path)
                except Exception:
                    pass

    async def _download_audio(self, video_id: str) -> Optional[str]:
        try:
            import yt_dlp
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            output = tmp.name.replace(".mp3", "")

            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": output,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "64",
                }],
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

            mp3_path = output + ".mp3"
            if os.path.exists(mp3_path):
                return mp3_path
            if os.path.exists(tmp.name):
                return tmp.name
            return None
        except Exception:
            return None

    async def _send_to_whisper(self, audio_path: str) -> Optional[str]:
        try:
            import httpx
            with open(audio_path, "rb") as f:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                        files={"file": (os.path.basename(audio_path), f, "audio/mpeg")},
                        data={"model": "whisper-1", "response_format": "json"}
                    )
                    if resp.status_code == 200:
                        return resp.json().get("text")
        except Exception:
            pass
        return None
