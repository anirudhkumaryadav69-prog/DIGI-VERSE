from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Optional

from app.core.config import settings


PayoutOutcome = Literal["success", "failure", "pending", "uncertain", "timeout"]


@dataclass(frozen=True)
class PayoutProviderRequest:
    payout_id: uuid.UUID
    amount: Decimal
    currency: str
    destination_masked: str
    provider_destination_reference: Optional[str]
    idempotency_key: str
    scenario: PayoutOutcome = "success"


@dataclass(frozen=True)
class PayoutProviderResponse:
    outcome: PayoutOutcome
    provider_reference: Optional[str] = None
    simulated: bool = True
    sanitized_error: Optional[str] = None
    retryable: bool = False


class PayoutProvider(ABC):
    provider_name: str

    @abstractmethod
    def execute(self, request: PayoutProviderRequest) -> PayoutProviderResponse:
        raise NotImplementedError


class MockPayoutProvider(PayoutProvider):
    provider_name = "mock"

    def execute(self, request: PayoutProviderRequest) -> PayoutProviderResponse:
        if settings.is_production:
            raise RuntimeError("Mock payout execution is forbidden in production.")
        if settings.ENVIRONMENT.strip().lower() not in {"test", "testing", "development", "dev", "local"}:
            raise RuntimeError("Mock payout execution is restricted to test or isolated development.")

        if request.scenario == "success":
            return PayoutProviderResponse(
                outcome="success",
                provider_reference=f"mock_payout_{uuid.uuid5(uuid.NAMESPACE_URL, request.idempotency_key).hex}",
                simulated=True,
                retryable=False,
            )
        if request.scenario == "failure":
            return PayoutProviderResponse(
                outcome="failure",
                provider_reference=None,
                simulated=True,
                sanitized_error="Simulated payout failure.",
                retryable=True,
            )
        if request.scenario == "pending":
            return PayoutProviderResponse(
                outcome="pending",
                provider_reference=f"mock_pending_{uuid.uuid5(uuid.NAMESPACE_URL, request.idempotency_key).hex}",
                simulated=True,
                retryable=False,
            )
        if request.scenario == "timeout":
            return PayoutProviderResponse(
                outcome="timeout",
                provider_reference=None,
                simulated=True,
                sanitized_error="Simulated provider timeout.",
                retryable=False,
            )
        return PayoutProviderResponse(
            outcome="uncertain",
            provider_reference=f"mock_uncertain_{uuid.uuid5(uuid.NAMESPACE_URL, request.idempotency_key).hex}",
            simulated=True,
            retryable=False,
        )


mock_payout_provider = MockPayoutProvider()
