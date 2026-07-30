import os
import re
import json
import time
import tempfile
import logging
from typing import Optional
import httpx
from app.config import settings
from app.schemas.pipeline_models import TranscriptResult

logger = logging.getLogger("clearlens.services.transcript")

_transcript_cache: dict[str, tuple[TranscriptResult, float]] = {}
_metadata_cache: dict[str, tuple[dict, float]] = {}
_CACHE_TTL = 86400
_http_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=15, limits=httpx.Limits(max_keepalive_connections=10, max_connections=20))
    return _http_client


class TranscriptService:
    async def extract(self, video_id: str) -> TranscriptResult:
        if video_id in _transcript_cache:
            cached, ts = _transcript_cache[video_id]
            if time.time() - ts < _CACHE_TTL:
                logger.info(f"Transcript cache hit for {video_id}")
                return cached
            del _transcript_cache[video_id]

        result = await self._fetch_youtube_transcript(video_id)
        if result:
            _transcript_cache[video_id] = (result, time.time())
            return result

        result = await self._fetch_youtube_captions(video_id)
        if result:
            _transcript_cache[video_id] = (result, time.time())
            return result

        result = await self._whisper_transcribe(video_id, provider="groq")
        if result:
            r = TranscriptResult(text=result, language="unknown", duration=0, source="groq_whisper")
            _transcript_cache[video_id] = (r, time.time())
            return r

        result = await self._whisper_transcribe(video_id, provider="openai")
        if result:
            r = TranscriptResult(text=result, language="unknown", duration=0, source="openai_whisper")
            _transcript_cache[video_id] = (r, time.time())
            return r

        return TranscriptResult(source=None)

    async def get_metadata(self, video_id: str) -> dict:
        if video_id in _metadata_cache:
            cached, ts = _metadata_cache[video_id]
            if time.time() - ts < _CACHE_TTL:
                return cached
            del _metadata_cache[video_id]
        try:
            client = _get_client()
            resp = await client.get(
                f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            )
            if resp.status_code == 200:
                data = resp.json()
                meta = {
                    "title": data.get("title", ""),
                    "channel": data.get("author_name", ""),
                    "thumbnail": data.get("thumbnail_url", ""),
                }
                _metadata_cache[video_id] = (meta, time.time())
                return meta
        except Exception as e:
            logger.debug(f"oEmbed metadata failed for {video_id}: {e}")
        return {}

    def _clean(self, text: str) -> str:
        text = re.sub(r"&#\d+;", "", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _deduplicate_lines(self, text: str) -> str:
        seen = set()
        lines = text.split(". ")
        unique = []
        for line in lines:
            normalized = re.sub(r"\s+", "", line.lower())[:60]
            if normalized not in seen:
                seen.add(normalized)
                unique.append(line)
        return ". ".join(unique)

    def _get_duration(self, segments: list) -> int:
        if not segments:
            return 0
        last = segments[-1]
        offset = last.get("offset", 0)
        dur = last.get("duration", 0)
        return int((offset + dur) / 1000) if dur else int(offset / 1000)

    async def _fetch_youtube_transcript(self, video_id: str) -> Optional[TranscriptResult]:
        client = _get_client()
        languages = ["hi", "en", "hinglish", "aae", "en-US", "en-GB"]
        for lang in languages:
            try:
                resp = await client.get(
                    f"https://youtubetranscript.com/api?vid={video_id}&lang={lang}"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        text = " ".join(seg.get("text", "") for seg in data)
                        text = self._clean(text)
                        text = self._deduplicate_lines(text)
                        duration = self._get_duration(data)
                        return TranscriptResult(text=text, language=lang, duration=duration, source="youtube_transcript")
                    if isinstance(data, dict) and "text" in data:
                        text = self._clean(data["text"])
                        return TranscriptResult(text=text, language=lang, duration=0, source="youtube_transcript")
            except Exception as e:
                logger.debug(f"YouTube transcript API failed for lang={lang}: {e}")
        return None

    async def _fetch_youtube_captions(self, video_id: str) -> Optional[TranscriptResult]:
        client = _get_client()
        try:
            resp = await client.get(
                f"https://youtubetranscript.com/api?vid={video_id}"
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    text = " ".join(seg.get("text", "") for seg in data)
                    text = self._clean(text)
                    text = self._deduplicate_lines(text)
                    duration = self._get_duration(data)
                    return TranscriptResult(text=text, language="en", duration=duration, source="youtube_caption")
                if isinstance(data, dict) and "text" in data:
                    text = self._clean(data["text"])
                    return TranscriptResult(text=text, language="en", duration=0, source="youtube_caption")
        except Exception as e:
            logger.debug(f"YouTube captions failed: {e}")
        return None

    async def _whisper_transcribe(self, video_id: str, provider: str = "groq") -> Optional[str]:
        if provider == "groq" and not settings.groq_api_key:
            return None
        if provider == "openai" and not settings.openai_api_key:
            return None
        audio_path = None
        try:
            audio_path = await self._download_audio(video_id)
            if not audio_path:
                return None
            if provider == "groq":
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
            logger.error(f"Whisper ({provider}) transcribe failed: {e}")
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
            ffmpeg_path = os.path.join(os.path.dirname(__file__), "..", "..", "ffmpeg.exe")
            if not os.path.exists(ffmpeg_path):
                ffmpeg_path = "ffmpeg"
            has_ffmpeg = False
            try:
                import subprocess
                subprocess.run([ffmpeg_path, "-version"], capture_output=True, timeout=5)
                has_ffmpeg = True
            except Exception:
                pass
            suffix = ".mp3" if has_ffmpeg else ".webm"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.close()
            output = tmp.name.replace(suffix, "")
            ydl_opts = {
                "outtmpl": output + ".%(ext)s",
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
            }
            if has_ffmpeg:
                ydl_opts["format"] = "bestaudio/best"
                ydl_opts["ffmpeg_location"] = ffmpeg_path
                ydl_opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "64"}]
            else:
                ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
            if has_ffmpeg:
                mp3_path = output + ".mp3"
                if os.path.exists(mp3_path):
                    return mp3_path
            else:
                for ext in (".m4a", ".webm", ".mp3", ".opus"):
                    path = output + ext
                    if os.path.exists(path) and os.path.getsize(path) > 0:
                        return path
            if os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 0:
                return tmp.name
            return None
        except Exception:
            return None

    async def _send_to_whisper(self, audio_path: str, api_key: str, model: str, endpoint: str) -> Optional[str]:
        try:
            client = _get_client()
            with open(audio_path, "rb") as f:
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