"""Logging setup.

Requirement from the spec: the backend logs collection, processing, heat,
lifecycle and every LLM call/error — but never the API key. A redaction filter
is attached to the root logger so a careless ``logger.info(cfg)`` cannot leak a
secret either.
"""

from __future__ import annotations

import logging
import re
import sys

_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|authorization|bearer|cookie|token)(\s*[=:]\s*)(\S+)"),
    re.compile(r"sk-[A-Za-z0-9\-_]{6,}"),
]
_CONFIGURED = False


def _redact(text: str) -> str:
    out = text
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            out = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}***REDACTED***", out)
        else:
            out = pattern.sub("***REDACTED***", out)
    return out


class SecretRedactionFilter(logging.Filter):
    """Strip anything that looks like a credential from a log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - defensive
            return True
        redacted = _redact(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    handler.addFilter(SecretRedactionFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    root.addFilter(SecretRedactionFilter())

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
