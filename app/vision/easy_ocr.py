import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger("clearlens.vision.easyocr")

_reader_instance = None
_reader_available = False

try:
    import easyocr
    _reader_available = True
except Exception as e:
    logger.warning(f"EasyOCR import failed: {e}")


def _get_reader():
    global _reader_instance
    if not _reader_available:
        return None
    if _reader_instance is None:
        try:
            _reader_instance = easyocr.Reader(["en"], gpu=False)
            logger.info("EasyOCR initialized (CPU mode)")
        except Exception as e:
            logger.error(f"EasyOCR init failed: {e}")
            return None
    return _reader_instance


async def ocr_image(image_data: bytes) -> Optional[str]:
    reader = _get_reader()
    if not reader:
        return None
    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.write(image_data)
        tmp.close()

        result = reader.readtext(tmp.name)
        if not result:
            return None

        lines = []
        for bbox, text, confidence in result:
            if confidence and confidence > 0.3:
                lines.append(text)
        return "\n".join(lines) if lines else None
    except Exception as e:
        logger.error(f"EasyOCR inference failed: {e}")
        return None
    finally:
        if tmp and os.path.exists(tmp.name):
            try:
                os.unlink(tmp.name)
            except Exception:
                pass


def is_available() -> bool:
    return _reader_available and _get_reader() is not None
