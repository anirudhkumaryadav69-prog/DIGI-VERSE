"""Structured JSON application logging with correlation IDs and automatic secret redaction."""
import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Optional

request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "digiverse_request_id", default=None
)

REDACTED_PLACEHOLDER = "[REDACTED]"
SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "otp",
    "authorization",
    "cookie",
    "signature",
    "private_download_url",
    "asset_storage_key",
    "storage_key",
    "access_key",
    "endpoint_url",
    "api_key",
    "service_role",
)


def redact_sensitive_data(data: Any) -> Any:
    """Recursively mask secret or credential fields so sensitive values are never logged."""
    if isinstance(data, dict):
        sanitized: dict[str, Any] = {}
        for k, v in data.items():
            kl = str(k).lower()
            if any(frag in kl for frag in SENSITIVE_KEY_FRAGMENTS):
                sanitized[str(k)] = REDACTED_PLACEHOLDER
            else:
                sanitized[str(k)] = redact_sensitive_data(v)
        return sanitized
    if isinstance(data, (list, tuple)):
        return [redact_sensitive_data(item) for item in data]
    return data


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        req_id = getattr(record, "request_id", None) or request_id_ctx.get()
        if req_id:
            payload["request_id"] = req_id
        event_data = getattr(record, "event_data", None)
        if isinstance(event_data, dict):
            payload["event"] = redact_sensitive_data(event_data)
        if record.exc_info:
            exc_type = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
            payload["exception_type"] = exc_type
        return json.dumps(payload, default=str)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("digiverse")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


app_logger = configure_logging()


def log_structured(
    level: int,
    message: str,
    *,
    category: str,
    details: Optional[dict[str, Any]] = None,
    exc_info: bool = False,
) -> None:
    app_logger.log(
        level,
        message,
        extra={
            "request_id": request_id_ctx.get(),
            "event_data": {"category": category, **(details or {})},
        },
        exc_info=exc_info,
    )


def log_security_event(event: str, **details: Any) -> None:
    log_structured(logging.INFO, event, category="security", details=details)


def log_payment_event(event: str, level: int = logging.INFO, **details: Any) -> None:
    log_structured(level, event, category="payment", details=details)


def log_background_event(event: str, level: int = logging.INFO, **details: Any) -> None:
    log_structured(level, event, category="background", details=details)


def log_db_error(event: str, **details: Any) -> None:
    log_structured(logging.ERROR, event, category="database", details=details, exc_info=True)
