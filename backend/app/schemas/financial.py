import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import StrictRequestModel


class SellerFinancialSummaryResponse(BaseModel):
    currency: str
    gross_sales: Decimal
    platform_commission: Decimal
    net_earnings: Decimal
    pending_earnings: Decimal
    available_earnings: Decimal
    refunded_amount: Decimal
    total_settled: Decimal


class SellerFinancialTransactionResponse(BaseModel):
    id: uuid.UUID
    transaction_type: str
    status: str
    currency: str
    debit_total: Decimal
    credit_total: Decimal
    order_id: Optional[uuid.UUID] = None
    payment_id: Optional[uuid.UUID] = None
    refund_record_id: Optional[uuid.UUID] = None
    provider_transaction_id: Optional[str] = None
    posted_at: datetime


class PaginatedSellerFinancialTransactionResponse(BaseModel):
    items: list[SellerFinancialTransactionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SellerOrderFinancialBreakdownResponse(BaseModel):
    order_id: uuid.UUID
    order_number: str
    currency: str
    gross_amount: Decimal
    commission_amount: Decimal
    net_amount: Decimal
    refunded_amount: Decimal
    settled_amount: Decimal = Decimal("0.00")
    paid_at: Optional[datetime] = None


class SellerOrderItemCommissionResponse(BaseModel):
    order_id: uuid.UUID
    order_item_id: uuid.UUID
    order_number: str
    product_name_snapshot: str
    gross_amount: Decimal
    commission_rate: Optional[Decimal] = None
    commission_amount: Decimal
    net_amount: Decimal
    commission_source: Optional[str] = None
    commission_snapshotted_at: Optional[datetime] = None


class PaginatedSellerOrderCommissionResponse(BaseModel):
    items: list[SellerOrderFinancialBreakdownResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SellerItemCommissionListResponse(BaseModel):
    items: list[SellerOrderItemCommissionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CommissionConfigurationResponse(BaseModel):
    default_rate: Decimal
    maximum_rate: Decimal
    currency: str
    precision_minor_units: int
    updated_at: datetime


class CommissionConfigurationUpdateRequest(StrictRequestModel):
    default_rate: Decimal = Field(..., ge=0, le=100)
    reason: Optional[str] = Field(default=None, max_length=2000)


class SellerCommissionConfigurationResponse(BaseModel):
    seller_id: uuid.UUID
    store_name: str
    store_slug: str
    override_rate: Optional[Decimal] = None
    effective_rate: Decimal
    currency: str
    updated_at: Optional[datetime] = None


class SellerCommissionUpdateRequest(StrictRequestModel):
    rate: Decimal = Field(..., ge=0, le=100)
    reason: Optional[str] = Field(default=None, max_length=2000)


class PaginatedSellerCommissionResponse(BaseModel):
    items: list[SellerCommissionConfigurationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CommissionHistoryResponse(BaseModel):
    id: uuid.UUID
    change_type: str
    seller_id: Optional[uuid.UUID] = None
    old_rate: Optional[Decimal] = None
    new_rate: Optional[Decimal] = None
    currency: str
    reason: Optional[str] = None
    changed_by_admin_id: Optional[uuid.UUID] = None
    created_at: datetime


class FinancialLedgerEntryResponse(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    transaction_type: str
    idempotency_key: str
    entry_type: str
    account_code: str
    direction: Literal["debit", "credit"]
    amount: Decimal
    currency: str
    order_id: Optional[uuid.UUID] = None
    order_item_id: Optional[uuid.UUID] = None
    payment_id: Optional[uuid.UUID] = None
    refund_record_id: Optional[uuid.UUID] = None
    seller_id: Optional[uuid.UUID] = None
    description: str
    posted_at: datetime


class PaginatedFinancialLedgerResponse(BaseModel):
    items: list[FinancialLedgerEntryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CommissionReportSellerResponse(BaseModel):
    seller_id: uuid.UUID
    store_name: str
    gross_sales: Decimal
    commission_amount: Decimal
    net_earnings: Decimal
    refunded_amount: Decimal


class CommissionReportResponse(BaseModel):
    currency: str
    default_rate: Decimal
    maximum_rate: Decimal
    sellers: list[CommissionReportSellerResponse]
