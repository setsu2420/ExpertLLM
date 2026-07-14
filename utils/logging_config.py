"""Minimal JSON logging setup to stdout."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime


def setup_json_logging(level: str = "INFO") -> logging.Logger:
    """Configure root logger to emit JSON to stdout; returns access logger."""
    root = logging.getLogger()
    root.handlers.clear()
    # 强制将默认/最低输出级别设为 WARNING，过滤掉 INFO 级别的常规访问日志。
    configured = getattr(logging, level.upper(), logging.INFO)
    min_level = logging.WARNING
    effective_level = configured if configured >= min_level else min_level
    root.setLevel(effective_level)

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            payload = {
                "timestamp": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            extra_fields = getattr(record, "extra_fields", None)
            if isinstance(extra_fields, dict):
                payload.update(extra_fields)
            if record.exc_info:
                payload["exc_info"] = self.formatException(record.exc_info)
            return json.dumps(payload, ensure_ascii=False)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    # 仅输出 WARNING 及以上到 stdout，避免 INFO 级别噪音
    handler.setLevel(effective_level)
    root.addHandler(handler)

    access_logger = logging.getLogger("access")
    access_logger.setLevel(effective_level)
    return access_logger
