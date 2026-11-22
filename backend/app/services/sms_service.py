"""SMS delivery provider abstraction with strict separation between development and production."""
from abc import ABC, abstractmethod
from typing import Optional

from app.core.config import settings


class SMSProvider(ABC):
    @abstractmethod
    def send_otp(self, phone_number: str, otp_code: str, expires_minutes: int) -> None:
        """Deliver an OTP code to an E.164 phone number."""


class DevelopmentSMSProvider(SMSProvider):
    """In-memory SMS sink for local development and automated test suites only.

    Never returns OTPs in production or writes them to application logs.
    """

    def __init__(self) -> None:
        self._outbox: dict[str, str] = {}
        self._send_count: int = 0

    def send_otp(self, phone_number: str, otp_code: str, expires_minutes: int) -> None:
        if settings.ENVIRONMENT.lower() == "production":
            raise RuntimeError("DevelopmentSMSProvider cannot be used in production.")
        self._outbox[phone_number] = otp_code
        self._send_count += 1

    def get_last_otp(self, phone_number: str) -> Optional[str]:
        if settings.ENVIRONMENT.lower() == "production":
            return None
        return self._outbox.get(phone_number)

    def clear(self) -> None:
        self._outbox.clear()
        self._send_count = 0


class ProductionSMSProvider(SMSProvider):
    """Production SMS gateway adapter placeholder.

    Never stores OTPs in memory or logs plaintext OTP values.
    """

    def send_otp(self, phone_number: str, otp_code: str, expires_minutes: int) -> None:
        # In production, integrate with verified SMS gateway SDK/HTTPS call without logging otp_code.
        return None


dev_sms_provider = DevelopmentSMSProvider()
prod_sms_provider = ProductionSMSProvider()


def get_sms_provider() -> SMSProvider:
    if settings.ENVIRONMENT.lower() == "production":
        return prod_sms_provider
    return dev_sms_provider
