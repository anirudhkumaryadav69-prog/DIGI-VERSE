import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import StrictRequestModel


class PayoutAccountCreateRequest(StrictRequestModel):
    account_type: Literal["bank", "upi"]
    display_name: str = Field(..., min_length=2, max_length=150)
    bank_name: Optional[str] = Field(default=None, max_length=150)
    masked_identifier: str = Field(..., min_length=4, max_length=64)
    provider_account_reference: Optional[str] = Field(default=None, max_length=255)
    is_default: bool = False

    @field_validator("display_name", "bank_name", "masked_identifier")
    @classmethod
    def _clean_optional_text(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = " ".join(v.strip().split())
        return cleaned or None


class PayoutAccountUpdateRequest(StrictRequestModel):
    display_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    bank_name: Optional[str] = Field(default=None, max_length=150)
    masked_identifier: Optional[str] = Field(default=None, min_length=4, max_length=64)
    provider_account_reference: Optional[str] = Field(default=None, max_length=255)


class PayoutAccountResponse(BaseModel):
    id: uuid.UUID
    seller_id: Optional[uuid.UUID] = None
    store_name: Optional[str] = None
    account_type: str
    display_name: str
    bank_name: Optional[str] = None
    masked_identifier: str
    verification_status: str
    is_default: bool
    is_active: bool
    verified_at: Optional[datetime] = None
    verification_reason: Optional[str] = None
    deactivated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PayoutBalanceResponse(BaseModel):
    currency: str
    seller_net_payable_signed: Decimal
    seller_net_payable: Decimal
    total_settled: Decimal
    reserved_amount: Decimal
    available_amount: Decimal
    debt_amount: Decimal
    minimum_amount: Decimal
    maximum_amount: Decimal
    live_execution_enabled: bool


class PayoutRequestCreate(StrictRequestModel):
    payout_account_id: uuid.UUID
    amount: Decimal = Field(..., gt=0)
    idempotency_key: Optional[str] = Field(default=None, max_length=160)


class PayoutRequestResponse(BaseModel):
    id: uuid.UUID
    seller_id: uuid.UUID
    payout_account_id: uuid.UUID
    amount: Decimal
    currency: str
    status: str
    reservation_status: str
    account_type_snapshot: str
    destination_masked_snapshot: str
    available_balance_snapshot: Decimal
    rejection_reason: Optional[str] = None
    failure_reason: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    processing_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    reconciliation_status: str = "not_required"
    reconciled_at: Optional[datetime] = None
    execution_status: Optional[str] = None
    settlement_status: Optional[str] = None
    settlement_reference: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PaginatedPayoutRequestResponse(BaseModel):
    items: list[PayoutRequestResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PayoutCancelRequest(StrictRequestModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class PayoutReviewRequest(StrictRequestModel):
    action: Literal["under_review"]
    reason: Optional[str] = Field(default=None, max_length=2000)


class PayoutApproveRequest(StrictRequestModel):
    reason: Optional[str] = Field(default=None, max_length=2000)


class PayoutRejectRequest(StrictRequestModel):
    reason: str = Field(..., min_length=3, max_length=2000)


class PayoutReportResponse(BaseModel):
    currency: str
    total_requests: int
    total_requested_amount: Decimal
    awaiting_review_amount: Decimal
    approved_amount: Decimal
    processing_amount: Decimal
    settled_amount: Decimal
    failed_amount: Decimal


class PayoutExecutionRequest(StrictRequestModel):
    scenario: Literal["success", "failure", "pending", "uncertain", "timeout"] = "success"
    idempotency_key: Optional[str] = Field(default=None, max_length=160)


class PayoutRetryRequest(StrictRequestModel):
    scenario: Literal["success", "failure", "pending", "uncertain", "timeout"] = "success"
    idempotency_key: Optional[str] = Field(default=None, max_length=160)


class PayoutReconcileRequest(StrictRequestModel):
    outcome: Literal["success", "failed"]
    provider_reference: Optional[str] = Field(default=None, max_length=255)


class PayoutExecutionAttemptResponse(BaseModel):
    id: uuid.UUID
    payout_request_id: uuid.UUID
    attempt_no: int
    idempotency_key: str
    provider_name: str
    provider_reference: Optional[str] = None
    status: str
    outcome: str
    retryable: bool
    uncertain: bool
    sanitized_error: Optional[str] = None
    simulated: bool
    executed_by_admin_id: Optional[uuid.UUID] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class SellerPayoutExecutionAttemptResponse(BaseModel):
    id: uuid.UUID
    attempt_no: int
    status: str
    outcome: str
    retryable: bool
    uncertain: bool
    simulated: bool
    sanitized_error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class PayoutAccountApproveRequest(StrictRequestModel):
    administrative_notes: Optional[str] = Field(default=None, max_length=2000)


class PayoutAccountRejectRequest(StrictRequestModel):
    reason: str = Field(..., min_length=3, max_length=2000)
    administrative_notes: Optional[str] = Field(default=None, max_length=2000)


class PayoutAccountVerificationHistoryResponse(BaseModel):
    id: uuid.UUID
    payout_account_id: uuid.UUID
    seller_id: uuid.UUID
    previous_status: str
    new_status: str
    administrator_id: uuid.UUID
    rejection_reason: Optional[str] = None
    administrative_notes: Optional[str] = None
    created_at: datetime


class PaginatedPayoutAccountVerificationResponse(BaseModel):
    items: list[PayoutAccountResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedPayoutAccountVerificationHistoryResponse(BaseModel):
    items: list[PayoutAccountVerificationHistoryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PayoutReconciliationLatestAttemptResponse(BaseModel):
    id: Optional[uuid.UUID] = None
    attempt_no: Optional[int] = None
    status: Optional[str] = None
    outcome: Optional[str] = None
    simulated: Optional[bool] = None
    provider_name: Optional[str] = None
    uncertain: Optional[bool] = None


class PayoutReconciliationSettlementResponse(BaseModel):
    transaction_id: uuid.UUID
    idempotency_key: str
    amount: Decimal
    currency: str
    posted_at: datetime
    mock_execution: bool


class PayoutReconciliationAttemptResponse(BaseModel):
    id: uuid.UUID
    attempt_no: int
    status: str
    outcome: str
    simulated: bool
    provider_name: str
    uncertain: bool
    retryable: bool
    sanitized_error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class PayoutReconciliationLedgerEntryResponse(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    account_code: str
    entry_type: str
    direction: str
    amount: Decimal
    currency: str
    seller_id: Optional[uuid.UUID] = None


class PayoutReconciliationHistoryResponse(BaseModel):
    id: uuid.UUID
    previous_classification: str
    new_classification: str
    resolution_action: str
    resolution_reason: str
    administrator_id: uuid.UUID
    evidence_reference: Optional[str] = None
    created_at: datetime


class PayoutReconciliationDetailResponse(BaseModel):
    classification: str
    secondary_issues: list[str]
    payout_id: uuid.UUID
    payout_status: str
    reconciliation_status: str
    latest_attempt: Optional[PayoutReconciliationLatestAttemptResponse] = None
    settlement: Optional[PayoutReconciliationSettlementResponse] = None
    settlement_count: int
    attempts: list[PayoutReconciliationAttemptResponse] = []
    ledger_entries: list[PayoutReconciliationLedgerEntryResponse] = []
    reconciliation_history: list[PayoutReconciliationHistoryResponse] = []
    masked_destination: str
    payout_account_id: uuid.UUID
    seller_id: uuid.UUID


class PaginatedPayoutReconciliationResponse(BaseModel):
    items: list[PayoutReconciliationDetailResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PayoutReconciliationSummaryResponse(BaseModel):
    currency: str
    total_payout_requests: int
    total_requested_amount: Decimal
    approved_amount: Decimal
    processing_amount: Decimal
    completed_amount: Decimal
    failed_amount: Decimal
    pending_amount: Decimal
    uncertain_amount: Decimal
    settled_amount: Decimal
    reserved_amount: Decimal
    outstanding_seller_debt: Decimal
    reconciliation_exception_count: int
    unresolved_discrepancy_count: int
    classification_counts: dict[str, int]
    classification_amounts: dict[str, Decimal]


class PayoutReconciliationResolveRequest(StrictRequestModel):
    resolution_action: Literal["investigate", "confirm_evidence", "keep_pending", "mark_resolved"]
    resolution_reason: str = Field(..., min_length=3, max_length=5000)
    evidence_reference: Optional[str] = Field(default=None, max_length=255)
    expected_classification: Optional[str] = Field(default=None, max_length=32)


class PayoutReconciliationResolveResponse(BaseModel):
    id: uuid.UUID
    payout_request_id: uuid.UUID
    previous_classification: str
    new_classification: str
    resolution_action: str
    resolution_reason: str
    administrator_id: uuid.UUID
    evidence_reference: Optional[str] = None
    created_at: datetime
