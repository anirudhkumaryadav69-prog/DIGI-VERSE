"""Transactional & marketing email provider abstraction.

Guarantees:
- Distinguishes `transactional` messages from `marketing` messages (consent + unsubscribe headers).
- Never includes confidential `private_download_url` or secrets in any email body.
- Transactional order/payment emails never block payment processing if an email error occurs.
- Marketing campaigns raise `EmailDeliveryError` on provider failure so campaigns are never falsely
  marked as delivered.
"""
import logging
import re
import uuid
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Literal, Optional

import httpx

from app.core.config import settings
from app.core.logging import log_background_event

EmailCategory = Literal["transactional", "marketing"]
PLACEHOLDER_EMAIL_KEYS = {"", "your_resend_api_key_placeholder"}
EMAIL_FORMAT_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailDeliveryError(RuntimeError):
    """Raised when email delivery fails or the production email provider is unconfigured."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "email_delivery_error",
        retryable: bool = True,
        status_code: Optional[int] = None,
        retry_after_seconds: Optional[int] = None,
        response_metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.response_metadata = response_metadata or {}


def _parse_retry_after(header_value: Optional[str]) -> Optional[int]:
    if not header_value:
        return None
    raw = header_value.strip()
    if raw.isdigit():
        return max(1, min(int(raw), settings.CAMPAIGN_RETRY_MAX_BACKOFF_SECONDS))
    return None


def render_commerce_email_template(template_name: str, context: dict[str, Any]) -> tuple[str, str]:
    """Render (subject, body) for transactional commerce notifications using safe context fields."""
    order_no = context.get("order_number", "")
    customer_name = context.get("customer_name", "Customer")
    amount = context.get("total_amount", "0.00")
    currency = context.get("currency", "INR")

    templates: dict[str, tuple[str, str]] = {
        "order_confirmation": (
            f"DIGI-VERSE Order Confirmation — {order_no}",
            (
                f"Hello {customer_name},\n\n"
                f"Your order {order_no} totaling {currency} {amount} has been created and is awaiting payment confirmation.\n"
                f"View your order status in your DIGI-VERSE account at /orders."
            ),
        ),
        "payment_success": (
            f"DIGI-VERSE Payment Confirmed — {order_no}",
            (
                f"Hello {customer_name},\n\n"
                f"We have verified your payment of {currency} {amount} for order {order_no}.\n"
                f"Your digital products are now unlocked in your account."
            ),
        ),
        "purchase_receipt": (
            f"DIGI-VERSE Official Purchase Receipt — {order_no}",
            (
                f"Hello {customer_name},\n\n"
                f"Thank you for your purchase on DIGI-VERSE.\n"
                f"Receipt for Order: {order_no}\n"
                f"Amount Paid: {currency} {amount}\n"
                f"Gateway Payment Reference: {context.get('gateway_payment_id', 'Verified')}\n"
                f"Access your invoice anytime in your account dashboard."
            ),
        ),
        "download_ready": (
            f"DIGI-VERSE Digital Downloads Ready — {order_no}",
            (
                f"Hello {customer_name},\n\n"
                f"Your purchased digital products for order {order_no} are ready for download.\n"
                f"Sign in to your DIGI-VERSE account and visit /downloads to generate your secure, short-lived download link."
            ),
        ),
        "payment_failed": (
            f"DIGI-VERSE Payment Unsuccessful — {order_no}",
            (
                f"Hello {customer_name},\n\n"
                f"We could not complete payment for order {order_no} ({currency} {amount}).\n"
                f"You may retry checkout from your shopping cart or orders page."
            ),
        ),
        "refund_confirmation": (
            f"DIGI-VERSE Refund Processed — {order_no}",
            (
                f"Hello {customer_name},\n\n"
                f"A refund of {currency} {amount} has been processed for order {order_no}.\n"
                f"Refund Reference: {context.get('refund_id', 'N/A')}."
            ),
        ),
    }
    return templates.get(
        template_name,
        (f"DIGI-VERSE Notification — {order_no}", f"Hello {customer_name}, update regarding {order_no}."),
    )


class EmailProvider(ABC):
    @abstractmethod
    def send_password_reset_email(self, email: str, reset_token: str, expires_minutes: int) -> None:
        """Deliver a single-use password reset token/link to the customer's email."""

    @abstractmethod
    def send_transactional_email(
        self,
        email: str,
        template_name: str,
        subject: str,
        body: str,
        metadata: Optional[dict[str, Any]] = None,
        category: EmailCategory = "transactional",
        idempotency_key: Optional[str] = None,
    ) -> str:
        """Deliver an email notification and return the provider message ID."""


class DevelopmentEmailProvider(EmailProvider):
    """In-memory email sink for development and automated testing only."""

    def __init__(self) -> None:
        self._reset_tokens: dict[str, str] = {}
        self.sent_notifications: list[dict[str, Any]] = []
        self.simulate_failure_for: set[str] = set()
        self.simulate_error_for: dict[str, EmailDeliveryError] = {}
        self._idempotency_cache: dict[str, str] = {}

    def send_password_reset_email(self, email: str, reset_token: str, expires_minutes: int) -> None:
        if settings.is_production:
            raise RuntimeError("DevelopmentEmailProvider cannot be used in production.")
        self._reset_tokens[email.lower()] = reset_token

    def get_last_reset_token(self, email: str) -> Optional[str]:
        if settings.is_production:
            return None
        return self._reset_tokens.get(email.lower())

    def send_transactional_email(
        self,
        email: str,
        template_name: str,
        subject: str,
        body: str,
        metadata: Optional[dict[str, Any]] = None,
        category: EmailCategory = "transactional",
        idempotency_key: Optional[str] = None,
    ) -> str:
        if settings.is_production:
            raise RuntimeError("DevelopmentEmailProvider cannot be used in production.")
        lower_email = (email or "").strip().lower()
        if not EMAIL_FORMAT_RE.match(lower_email):
            raise EmailDeliveryError(
                "Invalid recipient email address.",
                code="invalid_recipient",
                retryable=False,
            )
        if lower_email in self.simulate_error_for:
            raise self.simulate_error_for[lower_email]
        if "*" in self.simulate_error_for:
            raise self.simulate_error_for["*"]
        if lower_email in self.simulate_failure_for or "*" in self.simulate_failure_for:
            raise EmailDeliveryError(
                "Simulated email provider delivery failure.",
                code="simulated_failure",
                retryable=True,
            )
        if idempotency_key and idempotency_key in self._idempotency_cache:
            return self._idempotency_cache[idempotency_key]
        msg_id = f"re_dev_{uuid.uuid4().hex[:16]}"
        if idempotency_key:
            self._idempotency_cache[idempotency_key] = msg_id
        self.sent_notifications.append(
            {
                "email": lower_email,
                "template": template_name,
                "category": category,
                "subject": subject,
                "body": body,
                "provider_message_id": msg_id,
                "idempotency_key": idempotency_key,
                "metadata": metadata or {},
            }
        )
        return msg_id

    def clear(self) -> None:
        self._reset_tokens.clear()
        self.sent_notifications.clear()
        self.simulate_failure_for.clear()
        self.simulate_error_for.clear()
        self._idempotency_cache.clear()


class ProductionEmailProvider(EmailProvider):
    """Production Resend email adapter. Never logs raw reset tokens, API keys, or private URLs."""

    RESEND_API_URL = "https://api.resend.com/emails"

    def _require_api_key(self) -> str:
        key = (settings.RESEND_API_KEY or "").strip()
        if key in PLACEHOLDER_EMAIL_KEYS:
            raise EmailDeliveryError(
                "RESEND_API_KEY is not configured in the backend environment.",
                code="provider_unconfigured",
                retryable=False,
            )
        return key

    def _format_from_address(self) -> str:
        raw_email = (settings.RESEND_FROM_EMAIL or "").strip()
        if "<" in raw_email and ">" in raw_email:
            return raw_email
        sender_name = (settings.RESEND_FROM_NAME or "DIGI-VERSE").strip()
        return f"{sender_name} <{raw_email}>" if sender_name else raw_email

    def _dispatch_resend(
        self,
        *,
        to_email: str,
        subject: str,
        text_body: str,
        category: EmailCategory,
        headers: Optional[dict[str, str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        cleaned_email = (to_email or "").strip()
        if not EMAIL_FORMAT_RE.match(cleaned_email):
            raise EmailDeliveryError(
                "Invalid recipient email address format.",
                code="invalid_recipient",
                retryable=False,
            )
        api_key = self._require_api_key()
        payload: dict[str, Any] = {
            "from": self._format_from_address(),
            "to": [cleaned_email],
            "subject": subject,
            "text": text_body,
            "tags": [{"name": "category", "value": category}],
        }
        if headers:
            payload["headers"] = headers

        request_headers: dict[str, str] = {"Authorization": f"Bearer {api_key}"}
        if idempotency_key:
            request_headers["Idempotency-Key"] = idempotency_key[:120]

        timeout_s = float(settings.CAMPAIGN_PROVIDER_TIMEOUT_SECONDS or 10.0)
        try:
            with httpx.Client(timeout=timeout_s) as client:
                resp = client.post(
                    self.RESEND_API_URL,
                    json=payload,
                    headers=request_headers,
                )
        except httpx.TimeoutException as exc:
            log_background_event(
                "email.provider_timeout",
                level=logging.WARNING,
                category=category,
                error_type=exc.__class__.__name__,
            )
            raise EmailDeliveryError(
                f"Email provider timeout: {exc.__class__.__name__}",
                code="provider_timeout",
                retryable=True,
                response_metadata={"idempotency_supported": True},
            ) from exc
        except httpx.HTTPError as exc:
            log_background_event(
                "email.provider_network_error",
                level=logging.ERROR,
                category=category,
                error_type=exc.__class__.__name__,
            )
            raise EmailDeliveryError(
                f"Email provider network error: {exc.__class__.__name__}",
                code="provider_network_error",
                retryable=True,
                response_metadata={"idempotency_supported": True},
            ) from exc

        if resp.status_code == 429:
            retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
            log_background_event(
                "email.provider_rate_limited",
                level=logging.WARNING,
                category=category,
                status_code=429,
                retry_after_seconds=retry_after,
            )
            raise EmailDeliveryError(
                "Email provider rate limit exceeded (HTTP 429).",
                code="rate_limited",
                retryable=True,
                status_code=429,
                retry_after_seconds=retry_after,
                response_metadata={"status_code": 429, "idempotency_supported": True},
            )

        if resp.status_code >= 500 or resp.status_code in (408, 409, 425):
            log_background_event(
                "email.provider_transient_error",
                level=logging.WARNING,
                category=category,
                status_code=resp.status_code,
            )
            raise EmailDeliveryError(
                f"Email provider temporary error (HTTP {resp.status_code}).",
                code=f"http_{resp.status_code}",
                retryable=True,
                status_code=resp.status_code,
                response_metadata={"status_code": resp.status_code, "idempotency_supported": True},
            )

        if resp.status_code >= 400:
            log_background_event(
                "email.provider_rejected",
                level=logging.ERROR,
                category=category,
                status_code=resp.status_code,
            )
            raise EmailDeliveryError(
                f"Email provider rejected request (HTTP {resp.status_code}).",
                code=f"http_{resp.status_code}",
                retryable=False,
                status_code=resp.status_code,
                response_metadata={"status_code": resp.status_code, "idempotency_supported": True},
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise EmailDeliveryError(
                "Email provider returned invalid JSON response.",
                code="invalid_provider_response",
                retryable=False,
                status_code=resp.status_code,
            ) from exc

        msg_id = data.get("id") if isinstance(data, dict) else None
        if not msg_id:
            raise EmailDeliveryError(
                "Email provider response missing message ID.",
                code="missing_message_id",
                retryable=False,
                status_code=resp.status_code,
            )
        return str(msg_id)

    def send_password_reset_email(self, email: str, reset_token: str, expires_minutes: int) -> None:
        try:
            self._dispatch_resend(
                to_email=email,
                subject="DIGI-VERSE Password Reset Request",
                text_body=(
                    f"Use this single-use reset token within {expires_minutes} minutes "
                    f"to reset your DIGI-VERSE password:\n\n{reset_token}\n"
                ),
                category="transactional",
            )
        except EmailDeliveryError:
            # Never expose reset delivery failures to unauthenticated forgot-password callers
            return None

    def send_transactional_email(
        self,
        email: str,
        template_name: str,
        subject: str,
        body: str,
        metadata: Optional[dict[str, Any]] = None,
        category: EmailCategory = "transactional",
        idempotency_key: Optional[str] = None,
    ) -> str:
        headers = None
        if category == "marketing":
            headers = {"List-Unsubscribe": "<mailto:unsubscribe@digiverse.internal>"}
        return self._dispatch_resend(
            to_email=email,
            subject=subject,
            text_body=body,
            category=category,
            headers=headers,
            idempotency_key=idempotency_key,
        )


class DisabledEmailProvider(EmailProvider):
    """Fail-closed email provider when email delivery is intentionally disabled."""

    def send_password_reset_email(self, email: str, reset_token: str, expires_minutes: int) -> None:
        log_background_event("email.disabled_password_reset", level=logging.WARNING)
        raise EmailDeliveryError(
            "Email delivery is disabled in this environment.",
            code="email_disabled",
            retryable=False,
        )

    def send_transactional_email(
        self,
        email: str,
        template_name: str,
        subject: str,
        body: str,
        metadata: Optional[dict[str, Any]] = None,
        category: EmailCategory = "transactional",
        idempotency_key: Optional[str] = None,
    ) -> str:
        log_background_event(
            "email.disabled_dispatch",
            level=logging.WARNING,
            template=template_name,
            category=category,
        )
        raise EmailDeliveryError(
            "Email delivery is disabled in this environment.",
            code="email_disabled",
            retryable=False,
        )


dev_email_provider = DevelopmentEmailProvider()
prod_email_provider = ProductionEmailProvider()
disabled_email_provider = DisabledEmailProvider()


def get_email_provider() -> EmailProvider:
    if not settings.EMAIL_ENABLED:
        return disabled_email_provider
    if settings.is_production:
        return prod_email_provider
    key = (settings.RESEND_API_KEY or "").strip()
    if key not in PLACEHOLDER_EMAIL_KEYS:
        return prod_email_provider
    return dev_email_provider


def safe_send_commerce_notification(
    email: str,
    template_name: str,
    order_number: str,
    customer_name: str,
    total_amount: Decimal | str,
    currency: str = "INR",
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """Render and dispatch a transactional commerce email without ever blocking payment processing."""
    try:
        ctx: dict[str, Any] = {
            "order_number": order_number,
            "customer_name": customer_name,
            "total_amount": str(total_amount),
            "currency": currency,
        }
        if extra:
            for k, v in extra.items():
                if k != "private_download_url":
                    ctx[k] = v
        subject, body = render_commerce_email_template(template_name, ctx)
        get_email_provider().send_transactional_email(
            email=email,
            template_name=template_name,
            subject=subject,
            body=body,
            metadata=ctx,
            category="transactional",
        )
    except Exception:
        # Transactional email failure must never block or roll back an order or payment transaction
        log_background_event(
            "email.transactional_dispatch_failed",
            level=logging.WARNING,
            template=template_name,
            order_number=order_number,
        )
        return None
