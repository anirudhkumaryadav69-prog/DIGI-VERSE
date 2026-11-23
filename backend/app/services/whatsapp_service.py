"""WhatsApp Cloud API provider abstraction with strict separation between dev/test and production.

Security & reliability guarantees:
- Credentials (`WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`) are read only from backend env.
- Production mode never fabricates successful message IDs; fails explicitly if unconfigured or rejected.
- Distinguishes retryable rate-limit/transient errors from permanent validation failures.
- Documents idempotency boundaries: Meta Graph API does not support cross-request `Idempotency-Key`
  headers; pre-send `ConnectTimeout`/`ConnectError` are safely retried, whereas post-submission read
  timeouts are flagged ambiguous (`is_ambiguous_timeout=True`) rather than blindly re-sent.
"""
import logging
import re
import uuid
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.core.logging import log_background_event

PLACEHOLDER_WA_VALUES = {
    "",
    "your_whatsapp_cloud_api_token_placeholder",
    "your_whatsapp_phone_number_id_placeholder",
}
E164_PHONE_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")
GRAPH_VERSION_RE = re.compile(r"^v[0-9]+\.[0-9]+$")


class WhatsAppDeliveryError(RuntimeError):
    """Raised when WhatsApp Cloud API delivery fails or is unconfigured."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "whatsapp_delivery_error",
        retryable: bool = True,
        status_code: Optional[int] = None,
        retry_after_seconds: Optional[int] = None,
        is_ambiguous_timeout: bool = False,
        response_metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.is_ambiguous_timeout = is_ambiguous_timeout
        self.response_metadata = response_metadata or {}


def _parse_retry_after(header_value: Optional[str]) -> Optional[int]:
    if not header_value:
        return None
    raw = header_value.strip()
    if raw.isdigit():
        return max(1, min(int(raw), settings.CAMPAIGN_RETRY_MAX_BACKOFF_SECONDS))
    return None


class WhatsAppProvider(ABC):
    @abstractmethod
    def send_template_message(
        self,
        phone_number: str,
        approved_template_name: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        """Send an approved WhatsApp template message and return the provider message ID."""


class DevelopmentWhatsAppProvider(WhatsAppProvider):
    """In-memory WhatsApp sink for local development and automated test suites only."""

    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []
        self.simulate_failure_for: set[str] = set()
        self.simulate_error_for: dict[str, WhatsAppDeliveryError] = {}

    def send_template_message(
        self,
        phone_number: str,
        approved_template_name: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        if settings.is_production:
            raise RuntimeError("DevelopmentWhatsAppProvider cannot be used in production.")
        cleaned_phone = (phone_number or "").strip()
        if not E164_PHONE_RE.match(cleaned_phone):
            raise WhatsAppDeliveryError(
                "Invalid recipient phone number (expected E.164 format).",
                code="invalid_recipient",
                retryable=False,
            )
        if cleaned_phone in self.simulate_error_for:
            raise self.simulate_error_for[cleaned_phone]
        if "*" in self.simulate_error_for:
            raise self.simulate_error_for["*"]
        if cleaned_phone in self.simulate_failure_for or "*" in self.simulate_failure_for:
            raise WhatsAppDeliveryError(
                "Simulated WhatsApp provider delivery failure.",
                code="simulated_failure",
                retryable=True,
            )
        msg_id = f"wamid_dev_{uuid.uuid4().hex[:16]}"
        self.sent_messages.append(
            {
                "phone_number": cleaned_phone,
                "approved_template_name": approved_template_name,
                "content": content,
                "provider_message_id": msg_id,
                "idempotency_key": idempotency_key,
                "metadata": metadata or {},
            }
        )
        return msg_id

    def clear(self) -> None:
        self.sent_messages.clear()
        self.simulate_failure_for.clear()
        self.simulate_error_for.clear()


class MetaWhatsAppCloudProvider(WhatsAppProvider):
    """Meta WhatsApp Business Cloud API adapter."""

    def _messages_url(self, phone_id: str) -> str:
        version = (settings.WHATSAPP_GRAPH_API_VERSION or "v20.0").strip()
        if not GRAPH_VERSION_RE.match(version):
            version = "v20.0"
        return f"https://graph.facebook.com/{version}/{phone_id}/messages"

    def send_template_message(
        self,
        phone_number: str,
        approved_template_name: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        cleaned_phone = (phone_number or "").strip()
        if not E164_PHONE_RE.match(cleaned_phone):
            raise WhatsAppDeliveryError(
                "Invalid recipient phone number (expected E.164 format).",
                code="invalid_recipient",
                retryable=False,
            )
        token = (settings.WHATSAPP_ACCESS_TOKEN or "").strip()
        phone_id = (settings.WHATSAPP_PHONE_NUMBER_ID or "").strip()
        if token in PLACEHOLDER_WA_VALUES or phone_id in PLACEHOLDER_WA_VALUES:
            raise WhatsAppDeliveryError(
                "WhatsApp Cloud API credentials (WHATSAPP_ACCESS_TOKEN / WHATSAPP_PHONE_NUMBER_ID) are not configured.",
                code="provider_unconfigured",
                retryable=False,
            )

        payload = {
            "messaging_product": "whatsapp",
            "to": cleaned_phone.lstrip("+"),
            "type": "template",
            "template": {
                "name": approved_template_name,
                "language": {"code": "en"},
            },
        }
        timeout_s = float(settings.CAMPAIGN_PROVIDER_TIMEOUT_SECONDS or 10.0)
        try:
            with httpx.Client(timeout=timeout_s) as client:
                resp = client.post(
                    self._messages_url(phone_id),
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                )
        except (httpx.ConnectTimeout, httpx.ConnectError) as exc:
            # Connection never succeeded, so Meta never received this request; safe to retry.
            log_background_event(
                "whatsapp.provider_connect_error",
                level=logging.WARNING,
                error_type=exc.__class__.__name__,
            )
            raise WhatsAppDeliveryError(
                f"WhatsApp connection error: {exc.__class__.__name__}",
                code="provider_connect_error",
                retryable=True,
                is_ambiguous_timeout=False,
                response_metadata={"idempotency_supported": False},
            ) from exc
        except httpx.TimeoutException as exc:
            # Meta Graph API does not support Idempotency-Key deduplication on POST /messages.
            # Flag as ambiguous post-submission timeout to avoid blindly duplicating outbound WhatsApp alerts.
            log_background_event(
                "whatsapp.provider_ambiguous_timeout",
                level=logging.ERROR,
                error_type=exc.__class__.__name__,
            )
            raise WhatsAppDeliveryError(
                "WhatsApp request timed out after submission; retry suppressed to prevent duplicate messages without provider idempotency keys.",
                code="timeout_after_submission",
                retryable=False,
                is_ambiguous_timeout=True,
                response_metadata={
                    "idempotency_supported": False,
                    "ambiguity_note": "Meta Cloud API does not support Idempotency-Key; manual/webhook reconciliation required.",
                },
            ) from exc
        except httpx.HTTPError as exc:
            log_background_event(
                "whatsapp.provider_network_error",
                level=logging.ERROR,
                error_type=exc.__class__.__name__,
            )
            raise WhatsAppDeliveryError(
                f"WhatsApp network error: {exc.__class__.__name__}",
                code="provider_network_error",
                retryable=True,
                response_metadata={"idempotency_supported": False},
            ) from exc

        if resp.status_code == 429:
            retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
            log_background_event(
                "whatsapp.provider_rate_limited",
                level=logging.WARNING,
                status_code=429,
                retry_after_seconds=retry_after,
            )
            raise WhatsAppDeliveryError(
                "WhatsApp API rate limit exceeded (HTTP 429).",
                code="rate_limited",
                retryable=True,
                status_code=429,
                retry_after_seconds=retry_after,
                response_metadata={"status_code": 429, "idempotency_supported": False},
            )

        if resp.status_code >= 500 or resp.status_code in (408, 425):
            log_background_event(
                "whatsapp.provider_transient_error",
                level=logging.WARNING,
                status_code=resp.status_code,
            )
            raise WhatsAppDeliveryError(
                f"WhatsApp API temporary error (HTTP {resp.status_code}).",
                code=f"http_{resp.status_code}",
                retryable=True,
                status_code=resp.status_code,
                response_metadata={"status_code": resp.status_code, "idempotency_supported": False},
            )

        if resp.status_code >= 400:
            log_background_event(
                "whatsapp.provider_rejected",
                level=logging.ERROR,
                status_code=resp.status_code,
            )
            raise WhatsAppDeliveryError(
                f"WhatsApp API rejected message (HTTP {resp.status_code}).",
                code=f"http_{resp.status_code}",
                retryable=False,
                status_code=resp.status_code,
                response_metadata={"status_code": resp.status_code, "idempotency_supported": False},
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise WhatsAppDeliveryError(
                "WhatsApp API returned invalid JSON response.",
                code="invalid_provider_response",
                retryable=False,
                status_code=resp.status_code,
            ) from exc

        messages = data.get("messages") or [] if isinstance(data, dict) else []
        msg_id = messages[0].get("id") if messages and isinstance(messages[0], dict) else None
        if not msg_id:
            raise WhatsAppDeliveryError(
                "WhatsApp API response missing provider message ID.",
                code="missing_message_id",
                retryable=False,
                status_code=resp.status_code,
            )
        return str(msg_id)


class DisabledWhatsAppProvider(WhatsAppProvider):
    """Fail-closed WhatsApp provider when WhatsApp delivery is intentionally disabled."""

    def send_template_message(
        self,
        phone_number: str,
        approved_template_name: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        log_background_event("whatsapp.disabled_dispatch", level=logging.WARNING)
        raise WhatsAppDeliveryError(
            "WhatsApp delivery is disabled in this environment.",
            code="whatsapp_disabled",
            retryable=False,
        )


dev_whatsapp_provider = DevelopmentWhatsAppProvider()
prod_whatsapp_provider = MetaWhatsAppCloudProvider()
disabled_whatsapp_provider = DisabledWhatsAppProvider()


def get_whatsapp_provider() -> WhatsAppProvider:
    otp_provider = (settings.OTP_DELIVERY_PROVIDER or "").strip().lower()
    if otp_provider == "disabled" and not settings.WHATSAPP_OTP_ENABLED:
        return disabled_whatsapp_provider
    if settings.is_production:
        return prod_whatsapp_provider
    token = (settings.WHATSAPP_ACCESS_TOKEN or "").strip()
    phone_id = (settings.WHATSAPP_PHONE_NUMBER_ID or "").strip()
    if token not in PLACEHOLDER_WA_VALUES and phone_id not in PLACEHOLDER_WA_VALUES:
        return prod_whatsapp_provider
    return dev_whatsapp_provider
