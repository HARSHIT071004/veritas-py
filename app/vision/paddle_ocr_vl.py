import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger("clearlens.vision.paddleocr_vl")

_model = None
_processor = None
_available = False

try:
    from transformers import AutoModel, AutoProcessor
    _available = True
except Exception as e:
    logger.warning(f"PaddleOCR-VL (transformers) import failed: {e}")


def _load():
    global _model, _processor
    if not _available:
        return False
    if _model is not None:
        return True
    try:
        model_id = "PaddlePaddle/PaddleOCR-VL"
        logger.info(f"Loading {model_id}...")
        _processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        _model = AutoModel.from_pretrained(model_id, trust_remote_code=True)
        _model.eval()
        logger.info("PaddleOCR-VL loaded")
        return True
    except Exception as e:
        logger.error(f"PaddleOCR-VL load failed: {e}")
        return False


async def ocr_image(image_data: bytes) -> Optional[str]:
    if not _load():
        return None
    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.write(image_data)
        tmp.close()

        from PIL import Image
        image = Image.open(tmp.name).convert("RGB")
        inputs = _processor(images=image, return_tensors="pt")
        outputs = _model.generate(**inputs, max_new_tokens=512)
        text = _processor.decode(outputs[0], skip_special_tokens=True)
        return text.strip() if text and text.strip() else None
    except Exception as e:
        logger.error(f"PaddleOCR-VL inference failed: {e}")
        return None
    finally:
        if tmp and os.path.exists(tmp.name):
            try:
                os.unlink(tmp.name)
            except Exception:
                pass


def is_available() -> bool:
    return _available and _load()
