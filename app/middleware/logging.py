import logging
import json
import sys
from datetime import datetime
from typing import Optional


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    handlers = []
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(StructuredFormatter())
    handlers.append(stdout_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(StructuredFormatter())
        handlers.append(file_handler)

    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), handlers=handlers)

    for lib in ("httpx", "urllib3", "chromadb"):
        logging.getLogger(lib).setLevel(logging.WARNING)

    return logging.getLogger("clearlens")


logger = setup_logging()
