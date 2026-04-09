import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import settings
from app.request_context import get_trace_id


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id()
        return True


def setup_logging() -> None:
    log_format = "%(asctime)s | %(levelname)s | trace_id=%(trace_id)s | %(name)s | %(message)s"
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        filename=log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(log_format))

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter(log_format))

    logging.basicConfig(level=log_level, handlers=[stream_handler, file_handler], force=True)

    root = logging.getLogger()
    trace_filter = TraceIdFilter()
    for handler in root.handlers:
        handler.addFilter(trace_filter)
