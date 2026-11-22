"""Provider-independent payment gateway architecture with Razorpay and Mock (test-only) adapters.

Security guarantees:
- Never hardcodes credentials or exposes secret keys to the frontend.
- Verifies payment signatures and webhook signatures using constant-time HMAC-SHA256 (`secrets.compare_digest`).
- Never simulates successful payments in production; fails clearly if production/Razorpay credentials are unconfigured.
"""
import hashlib
import hmac
import secrets
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.logging import log_payment_event

PLACEHOLDER_VALUES = {
    "",
    "your_razorpay_key_id_placeholder",
    "your_razorpay_key_secret_placeholder",
    "your_razorpay_webhook_secret_placeholder",
}

MOCK_TEST_SECRET = "digiverse_mock_gateway_hmac_secret_test_only"
MOCK_WEBHOOK_SECRET = "digiverse_mock_webhook_hmac_secret_test_only"


@dataclass
class GatewayOrderInitResult:
    gateway_name: str
    gateway_order_id: str
    public_key_id: str
    amount_subunits: int
    currency: str
    metadata: dict[str, Any]


@dataclass
class GatewayRefundResult:
    refund_id: str
    status: str
    amount_subunits: int


class PaymentGatewayProvider(ABC):
    gateway_name: str

    @abstractmethod
    def create_order(
        self,
        order_number: str,
        amount: Decimal,
        currency: str,
        notes: Optional[dict[str, str]] = None,
    ) -> GatewayOrderInitResult:
        """Initialize a payment order with the gateway and return safe client initialization data."""

    @abstractmethod
    def verify_payment_signature(
        self,
        gateway_order_id: str,
        gateway_payment_id: str,
        signature: str,
    ) -> bool:
        """Cryptographically verify the payment signature returned after checkout."""

    @abstractmethod
    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        """Cryptographically verify a raw webhook payload signature."""

    @abstractmethod
    def initiate_refund(
        self,
        gateway_payment_id: str,
        amount: Decimal,
    ) -> GatewayRefundResult:
        """Initiate a full or partial refund through the payment provider."""


def amount_to_subunits(amount: Decimal) -> int:
    """Convert a Decimal major-currency amount (e.g. INR 499.00) to integer subunits (paise = 49900)."""
    return int((Decimal(str(amount)) * Decimal("100")).to_integral_value())


class RazorpayPaymentProvider(PaymentGatewayProvider):
    """Official Razorpay Orders, Signature Verification, Webhooks & Refunds integration."""

    gateway_name = "razorpay"
    BASE_URL = "https://api.razorpay.com/v1"

    def _require_credentials(self) -> tuple[str, str]:
        key_id = (settings.RAZORPAY_KEY_ID or "").strip()
        key_secret = (settings.RAZORPAY_KEY_SECRET or "").strip()
        if key_id in PLACEHOLDER_VALUES or key_secret in PLACEHOLDER_VALUES:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Razorpay payment gateway credentials (RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET) "
                    "are not configured in the backend environment."
                ),
            )
        return key_id, key_secret

    def create_order(
        self,
        order_number: str,
        amount: Decimal,
        currency: str,
        notes: Optional[dict[str, str]] = None,
    ) -> GatewayOrderInitResult:
        key_id, key_secret = self._require_credentials()
        subunits = amount_to_subunits(amount)
        payload = {
            "amount": subunits,
            "currency": currency,
            "receipt": order_number,
            "notes": notes or {},
        }
        try:
            with httpx.Client(timeout=10.0, auth=(key_id, key_secret)) as client:
                resp = client.post(f"{self.BASE_URL}/orders", json=payload)
        except httpx.HTTPError as exc:
            log_payment_event(
                "razorpay.create_order_network_error",
                order_number=order_number,
                error_type=exc.__class__.__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to reach Razorpay payment gateway.",
            ) from exc

        if resp.status_code >= 400:
            log_payment_event(
                "razorpay.create_order_rejected",
                order_number=order_number,
                status_code=resp.status_code,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Razorpay rejected payment order initialization.",
            )

        data = resp.json()
        return GatewayOrderInitResult(
            gateway_name=self.gateway_name,
            gateway_order_id=data["id"],
            public_key_id=key_id,
            amount_subunits=int(data["amount"]),
            currency=data["currency"],
            metadata={"razorpay_status": data.get("status", "created")},
        )

    def verify_payment_signature(
        self,
        gateway_order_id: str,
        gateway_payment_id: str,
        signature: str,
    ) -> bool:
        _, key_secret = self._require_credentials()
        message = f"{gateway_order_id}|{gateway_payment_id}".encode("utf-8")
        expected = hmac.new(key_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
        return secrets.compare_digest(expected, (signature or "").strip())

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        webhook_secret = (settings.RAZORPAY_WEBHOOK_SECRET or "").strip()
        if webhook_secret in PLACEHOLDER_VALUES:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="RAZORPAY_WEBHOOK_SECRET is not configured.",
            )
        expected = hmac.new(webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return secrets.compare_digest(expected, (signature or "").strip())

    def initiate_refund(
        self,
        gateway_payment_id: str,
        amount: Decimal,
    ) -> GatewayRefundResult:
        key_id, key_secret = self._require_credentials()
        subunits = amount_to_subunits(amount)
        try:
            with httpx.Client(timeout=10.0, auth=(key_id, key_secret)) as client:
                resp = client.post(
                    f"{self.BASE_URL}/payments/{gateway_payment_id}/refund",
                    json={"amount": subunits},
                )
        except httpx.HTTPError as exc:
            log_payment_event(
                "razorpay.refund_network_error",
                gateway_payment_id=gateway_payment_id,
                error_type=exc.__class__.__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to reach Razorpay for refund processing.",
            ) from exc

        if resp.status_code >= 400:
            log_payment_event(
                "razorpay.refund_rejected",
                gateway_payment_id=gateway_payment_id,
                status_code=resp.status_code,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Razorpay refund request failed.",
            )
        data = resp.json()
        return GatewayRefundResult(
            refund_id=data["id"],
            status=data.get("status", "processed"),
            amount_subunits=int(data.get("amount", subunits)),
        )


class MockPaymentProvider(PaymentGatewayProvider):
    """Deterministic HMAC-verified payment provider exclusively for automated tests & sandbox verification.

    Strictly blocked if ENVIRONMENT == 'production'.
    """

    gateway_name = "mock"

    def _ensure_non_production(self) -> None:
        if settings.is_production:
            raise RuntimeError("MockPaymentProvider is forbidden in production.")

    def create_order(
        self,
        order_number: str,
        amount: Decimal,
        currency: str,
        notes: Optional[dict[str, str]] = None,
    ) -> GatewayOrderInitResult:
        self._ensure_non_production()
        subunits = amount_to_subunits(amount)
        gateway_order_id = f"order_mock_{uuid.uuid4().hex[:16]}"
        return GatewayOrderInitResult(
            gateway_name=self.gateway_name,
            gateway_order_id=gateway_order_id,
            public_key_id="rzp_test_mock_public_key",
            amount_subunits=subunits,
            currency=currency,
            metadata={"receipt": order_number, "notes": notes or {}},
        )

    @staticmethod
    def sign_payment(gateway_order_id: str, gateway_payment_id: str) -> str:
        msg = f"{gateway_order_id}|{gateway_payment_id}".encode("utf-8")
        return hmac.new(MOCK_TEST_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    @staticmethod
    def sign_webhook(raw_body: bytes) -> str:
        return hmac.new(MOCK_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    def verify_payment_signature(
        self,
        gateway_order_id: str,
        gateway_payment_id: str,
        signature: str,
    ) -> bool:
        self._ensure_non_production()
        expected = self.sign_payment(gateway_order_id, gateway_payment_id)
        return secrets.compare_digest(expected, (signature or "").strip())

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        self._ensure_non_production()
        expected = self.sign_webhook(raw_body)
        return secrets.compare_digest(expected, (signature or "").strip())

    def initiate_refund(
        self,
        gateway_payment_id: str,
        amount: Decimal,
    ) -> GatewayRefundResult:
        self._ensure_non_production()
        return GatewayRefundResult(
            refund_id=f"rfnd_mock_{uuid.uuid4().hex[:14]}",
            status="processed",
            amount_subunits=amount_to_subunits(amount),
        )


razorpay_provider = RazorpayPaymentProvider()
mock_payment_provider = MockPaymentProvider()


def get_payment_provider() -> PaymentGatewayProvider:
    provider_name = (settings.PAYMENT_PROVIDER or "razorpay").strip().lower()
    if provider_name == "mock":
        if settings.is_production:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Mock payment provider cannot be used in production.",
            )
        return mock_payment_provider
    return razorpay_provider
