import os
import re
import tempfile
import logging
from typing import Optional
from app.config import settings
from app.schemas.pipeline_models import TranscriptResult

logger = logging.getLogger("clearlens.services.transcript")


class TranscriptService:
    async def extract(self, video_id: str) -> TranscriptResult:
        result = await self._fetch_transcript(video_id)
        if result:
            return TranscriptResult(**result, source="youtube_api")
        text = await self._whisper_transcribe(video_id)
        if text:
            return TranscriptResult(text=text, language="unknown", duration=0, source="whisper")
        return TranscriptResult(source=None)

    def _clean(self, text: str) -> str:
        text = re.sub(r"&#\d+;", "", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _get_duration(self, segments: list) -> int:
        if not segments:
            return 0
        last = segments[-1]
        offset = last.get("offset", 0)
        dur = last.get("duration", 0)
        return int((offset + dur) / 1000) if dur else int(offset / 1000)

    async def _fetch_transcript(self, video_id: str) -> Optional[dict]:
        import httpx
        languages = ["hi", "en", "hinglish", "aae", "en-US", "en-GB"]
        for lang in languages:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"https://youtubetranscript.com/api?vid={video_id}&lang={lang}",
                        timeout=10
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, list):
                            text = " ".join(seg.get("text", "") for seg in data)
                            text = self._clean(text)
                            duration = self._get_duration(data)
                            return {"text": text, "language": lang, "duration": duration}
                        if isinstance(data, dict) and "text" in data:
                            text = self._clean(data["text"])
                            return {"text": text, "language": lang, "duration": 0}
            except Exception as e:
                logger.debug(f"YouTube transcript API failed for lang={lang}: {e}")
        return None

    async def _whisper_transcribe(self, video_id: str) -> Optional[str]:
        if not settings.groq_api_key and not settings.openai_api_key:
            return None
        audio_path = None
        try:
            audio_path = await self._download_audio(video_id)
            if not audio_path:
                return None
            if settings.groq_api_key:
                return await self._send_to_whisper(
                    audio_path, api_key=settings.groq_api_key,
                    model=settings.groq_stt_model,
                    endpoint="https://api.groq.com/openai/v1/audio/transcriptions"
                )
            return await self._send_to_whisper(
                audio_path, api_key=settings.openai_api_key,
                model="whisper-1",
                endpoint="https://api.openai.com/v1/audio/transcriptions"
            )
        except Exception as e:
            logger.error(f"Whisper transcribe failed: {e}")
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
            ffmpeg_path = os.path.join(os.path.dirname(__file__), "..", "..", "ffmpeg.exe")
            if not os.path.exists(ffmpeg_path):
                ffmpeg_path = "ffmpeg"
            ydl_opts = {
                "format": "bestaudio/best", "outtmpl": output,
                "ffmpeg_location": ffmpeg_path,
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "64"}],
                "quiet": True, "no_warnings": True,
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

    async def _send_to_whisper(self, audio_path: str, api_key: str, model: str, endpoint: str) -> Optional[str]:
        try:
            import httpx
            with open(audio_path, "rb") as f:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        endpoint,
                        headers={"Authorization": f"Bearer {api_key}"},
                        files={"file": (os.path.basename(audio_path), f, "audio/mpeg")},
                        data={"model": model, "response_format": "json"}
                    )
                    if resp.status_code == 200:
                        return resp.json().get("text")
        except Exception:
            pass
        return None
