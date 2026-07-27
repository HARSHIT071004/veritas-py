import logging
import os
import tempfile
from typing import Optional
from app.config import settings

logger = logging.getLogger("clearlens.vision.frames")


async def extract_frames(video_id: str, max_frames: int = 5) -> Optional[list[bytes]]:
    if not settings.opencv_frames_enabled:
        return None
    video_path = None
    try:
        video_path = await _download_video(video_id)
        if not video_path:
            return None
        return _extract_frames_opencv(video_path, max_frames)
    except Exception as e:
        logger.error(f"Frame extraction failed: {e}")
        return None
    finally:
        if video_path and os.path.exists(video_path):
            try:
                os.unlink(video_path)
            except Exception:
                pass


def _extract_frames_opencv(video_path: str, max_frames: int) -> list[bytes]:
    import cv2
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    interval = max(1, settings.opencv_frame_interval)
    step = max(1, total // (max_frames * interval)) if total > max_frames else 1

    frames = []
    count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if count % step == 0:
            success, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if success:
                frames.append(buf.tobytes())
                if len(frames) >= max_frames:
                    break
        count += 1

    cap.release()
    logger.info(f"Extracted {len(frames)} frames from {total} total frames ({fps:.1f} fps)")
    return frames


    async def _download_video(video_id: str) -> Optional[str]:
        try:
            import yt_dlp
            tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            tmp.close()
            out = tmp.name.replace(".mp4", "")

            ffmpeg_path = os.path.join(os.path.dirname(__file__), "..", "..", "ffmpeg.exe")
            ffmpeg_path = os.path.abspath(ffmpeg_path)
            if not os.path.exists(ffmpeg_path):
                ffmpeg_path = "ffmpeg"

            ydl_opts = {
                "format": "worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst[ext=mp4]/worst",
                "outtmpl": out + ".%(ext)s",
                "ffmpeg_location": ffmpeg_path,
                "quiet": True,
                "no_warnings": True,
                "max_filesize": 50 * 1024 * 1024,
            }
        loop = None
        try:
            import asyncio
            loop = asyncio.get_event_loop()
        except Exception:
            pass

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
            mp4 = out + ".mp4"
            webm = out + ".webm"
            if os.path.exists(mp4):
                return mp4
            if os.path.exists(webm):
                return webm
            return None

        if loop and loop.is_running():
            return await loop.run_in_executor(None, _download)
        return _download()
    except Exception as e:
        logger.error(f"Video download failed: {e}")
        return None
