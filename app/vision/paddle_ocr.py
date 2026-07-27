import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger("clearlens.vision")

_ocr_instance = None
_ocr_available = False

try:
    from paddleocr import PaddleOCR
    _ocr_available = True
except Exception as e:
    logger.warning(f"PaddleOCR import failed: {e}. Gemini fallback will be used.")


def _get_ocr():
    global _ocr_instance
    if not _ocr_available:
        return None
    if _ocr_instance is None:
        try:
            _ocr_instance = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False, show_log=False)
            logger.info("PaddleOCR initialized (CPU mode)")
        except Exception as e:
            logger.error(f"PaddleOCR init failed: {e}")
            return None
    return _ocr_instance


async def ocr_image(image_data: bytes) -> Optional[str]:
    ocr = _get_ocr()
    if not ocr:
        return None
    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.write(image_data)
        tmp.close()

        result = ocr.ocr(tmp.name, cls=True)
        if not result or not result[0]:
            return None

        lines = []
        for line_group in result:
            if not line_group:
                continue
            for word_info in line_group:
                if len(word_info) >= 2 and word_info[1] and len(word_info[1]) >= 2:
                    text, confidence = word_info[1]
                    if confidence and confidence > 0.3:
                        lines.append(text)
        return "\n".join(lines) if lines else None
    except Exception as e:
        logger.error(f"PaddleOCR inference failed: {e}")
        return None
    finally:
        if tmp and os.path.exists(tmp.name):
            try:
                os.unlink(tmp.name)
            except Exception:
                pass


def is_available() -> bool:
    return _ocr_available and _get_ocr() is not None
