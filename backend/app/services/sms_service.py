"""SMS/WhatsApp OTP delivery provider abstraction.

Development delivery is an isolated in-memory diagnostic sink.
WhatsApp delivery uses Meta Cloud API only when explicitly enabled.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import httpx

from app.core.config import settings


@dataclass(frozen=True)
class SMSDeliveryResult:
    status: str
    provider: str
    provider_message_id: Optional[str] = None
    safe_detail: Optional[str] = None


class SMSProvider(ABC):
    @abstractmethod
    def send_otp(self, phone_number: str, otp_code: str, expires_minutes: int) -> SMSDeliveryResult:
        """Deliver an OTP code to an E.164 phone number."""


class DevelopmentSMSProvider(SMSProvider):
    """In-memory SMS sink for local development and automated test suites only.

    Never returns OTPs in production or writes them to application logs.
    """

    def __init__(self) -> None:
        self._outbox: dict[str, str] = {}
        self._send_count: int = 0

    def send_otp(self, phone_number: str, otp_code: str, expires_minutes: int) -> SMSDeliveryResult:
        if settings.ENVIRONMENT.lower() == "production":
            raise RuntimeError("DevelopmentSMSProvider cannot be used in production.")
        self._outbox[phone_number] = otp_code
        self._send_count += 1
        if settings.ENABLE_DEV_OTP:
            masked = phone_number[:4] + "*" * max(0, len(phone_number) - 8) + phone_number[-4:]
            print(
                f"[LOCAL DEVELOPMENT OTP] Phone {masked}; code {otp_code}; "
                f"expires in {expires_minutes} minutes.",
                flush=True,
            )
        return SMSDeliveryResult(
            status="development_only",
            provider="development",
            safe_detail="OTP is available in the local backend terminal.",
        )

    def get_last_otp(self, phone_number: str) -> Optional[str]:
        if settings.ENVIRONMENT.lower() == "production":
            return None
        return self._outbox.get(phone_number)

    def clear(self) -> None:
        self._outbox.clear()
        self._send_count = 0


class WhatsAppCloudSMSProvider(SMSProvider):
    """Meta WhatsApp Cloud API OTP authentication-template provider."""

    def send_otp(self, phone_number: str, otp_code: str, expires_minutes: int) -> SMSDeliveryResult:
        if not settings.WHATSAPP_OTP_ENABLED:
            return SMSDeliveryResult(
                status="disabled",
                provider="whatsapp",
                safe_detail="WhatsApp OTP delivery is disabled.",
            )

        placeholder_values = {"", "your_whatsapp_cloud_api_token_placeholder", "your_whatsapp_phone_number_id_placeholder"}
        access_token = (settings.WHATSAPP_ACCESS_TOKEN or "").strip()
        phone_number_id = (settings.WHATSAPP_PHONE_NUMBER_ID or "").strip()
        template_name = (settings.WHATSAPP_TEMPLATE_NAME or "").strip()
        template_language = (settings.WHATSAPP_TEMPLATE_LANGUAGE or "en_US").strip()

        if access_token in placeholder_values or not access_token:
            return SMSDeliveryResult(
                status="failed",
                provider="whatsapp",
                safe_detail="WhatsApp OTP provider is not configured.",
            )
        if phone_number_id in placeholder_values or not phone_number_id:
            return SMSDeliveryResult(
                status="failed",
                provider="whatsapp",
                safe_detail="WhatsApp OTP provider is not configured.",
            )
        if not template_name or template_name.startswith("your_"):
            return SMSDeliveryResult(
                status="failed",
                provider="whatsapp",
                safe_detail="WhatsApp authentication template is not configured.",
            )

        endpoint = (
            f"https://graph.facebook.com/{settings.WHATSAPP_GRAPH_API_VERSION or 'v27.0'}/"
            f"{phone_number_id}/messages"
        )
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number.lstrip("+"),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": template_language},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": otp_code}],
                    },
                    {
                        "type": "button",
                        "sub_type": "url",
                        "index": "0",
                        "parameters": [{"type": "text", "text": otp_code}],
                    },
                ],
            },
        }
        try:
            with httpx.Client(timeout=settings.WHATSAPP_REQUEST_TIMEOUT_SECONDS) as client:
                response = client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException:
            return SMSDeliveryResult(
                status="failed",
                provider="whatsapp",
                safe_detail="WhatsApp OTP request timed out.",
            )
        except httpx.HTTPError:
            return SMSDeliveryResult(
                status="failed",
                provider="whatsapp",
                safe_detail="WhatsApp OTP request could not reach the provider.",
            )

        if response.status_code >= 400:
            if response.status_code in (401, 403):
                safe_detail = "WhatsApp OTP provider authentication was rejected."
            elif response.status_code == 429:
                safe_detail = "WhatsApp OTP provider rate limit was reached."
            elif response.status_code >= 500:
                safe_detail = "WhatsApp OTP provider is temporarily unavailable."
            else:
                safe_detail = "WhatsApp OTP request was rejected."
            return SMSDeliveryResult(status="failed", provider="whatsapp", safe_detail=safe_detail)

        try:
            data = response.json()
            messages = data.get("messages") if isinstance(data, dict) else None
            message_id = messages[0].get("id") if isinstance(messages, list) and messages else None
        except (ValueError, AttributeError, IndexError):
            return SMSDeliveryResult(
                status="failed",
                provider="whatsapp",
                safe_detail="WhatsApp returned an invalid provider response.",
            )
        if not message_id:
            return SMSDeliveryResult(
                status="failed",
                provider="whatsapp",
                safe_detail="WhatsApp did not accept the OTP request.",
            )
        return SMSDeliveryResult(
            status="accepted",
            provider="whatsapp",
            provider_message_id=str(message_id),
            safe_detail="WhatsApp accepted the OTP message.",
        )


class DisabledSMSProvider(SMSProvider):
    """Honest OTP provider when WhatsApp OTP delivery is intentionally disabled."""

    def send_otp(self, phone_number: str, otp_code: str, expires_minutes: int) -> SMSDeliveryResult:
        return SMSDeliveryResult(
            status="disabled",
            provider="disabled",
            safe_detail="Phone OTP delivery via WhatsApp is currently unavailable.",
        )


dev_sms_provider = DevelopmentSMSProvider()
whatsapp_sms_provider = WhatsAppCloudSMSProvider()
disabled_sms_provider = DisabledSMSProvider()


def get_sms_provider() -> SMSProvider:
    provider = (settings.OTP_DELIVERY_PROVIDER or "development").strip().lower()
    environment = settings.ENVIRONMENT.lower()
    if provider == "disabled":
        if settings.WHATSAPP_OTP_ENABLED:
            raise RuntimeError("WHATSAPP_OTP_ENABLED cannot be True when OTP_DELIVERY_PROVIDER is 'disabled'.")
        return disabled_sms_provider
    if environment == "production":
        if provider != "whatsapp" or not settings.WHATSAPP_OTP_ENABLED:
            raise RuntimeError("Production OTP delivery must use explicitly enabled WhatsApp or 'disabled'.")
        return whatsapp_sms_provider
    if provider == "whatsapp" and settings.WHATSAPP_OTP_ENABLED:
        return whatsapp_sms_provider
    if environment == "development" and settings.ENABLE_DEV_OTP:
        return dev_sms_provider
    if environment in ("test", "testing") and provider == "development":
        return dev_sms_provider
    raise RuntimeError("OTP delivery provider is disabled or misconfigured.")
