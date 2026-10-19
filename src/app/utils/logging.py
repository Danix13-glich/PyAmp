from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .paths import LOGS_DIR, ensure_app_dirs

LOG_FILENAME = "pyamp.log"
MAX_BYTES = 1_000_000  # 1 MB
BACKUP_COUNT = 5
FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> str:
    ensure_app_dirs()
    log_file = LOGS_DIR / LOG_FILENAME

    root = logging.getLogger()
    root.setLevel(level)
    formatter = logging.Formatter(FORMAT, datefmt=DATEFMT)

    has_file_handler = any(isinstance(handler, RotatingFileHandler) for handler in root.handlers)
    if not has_file_handler:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    return str(log_file)
