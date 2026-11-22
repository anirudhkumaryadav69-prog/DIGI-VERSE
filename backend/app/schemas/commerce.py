import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DownloadStatus, OrderPaymentStatus, OrderStatus, PaymentStatus
from app.schemas.auth import StrictRequestModel
from app.schemas.catalog import ActiveDiscountPublicResponse


# ---------------------------------------------------------------------------
# Wishlist Schemas
# ---------------------------------------------------------------------------


class WishlistItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    product_slug: str
    category_name: str
    image_url: Optional[str] = None
    original_price: Decimal
    effective_price: Decimal
    is_on_sale: bool
    active_discount: Optional[ActiveDiscountPublicResponse] = None
    is_available: bool
    created_at: datetime


class WishlistResponse(BaseModel):
    items: list[WishlistItemResponse]
    total_items: int


# ---------------------------------------------------------------------------
# Persistent Shopping Cart Schemas
# ---------------------------------------------------------------------------


class CartItemAddRequest(StrictRequestModel):
    product_id: uuid.UUID
    quantity: int = Field(default=1, ge=1, le=100)


class CartItemUpdateRequest(StrictRequestModel):
    quantity: int = Field(..., ge=1, le=100)


class CartItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    product_slug: str
    category_name: str
    thumbnail_url: Optional[str] = None
    unit_price: Decimal
    active_discount: Optional[ActiveDiscountPublicResponse] = None
    effective_unit_price: Decimal
    quantity: int
    line_subtotal: Decimal
    line_discount: Decimal
    line_total: Decimal
    is_available: bool


class CartResponse(BaseModel):
    cart_id: uuid.UUID
    customer_id: uuid.UUID
    currency: str
    items: list[CartItemResponse]
    total_quantity: int
    subtotal: Decimal
    total_discount: Decimal
    final_payable_amount: Decimal
    updated_at: datetime


# ---------------------------------------------------------------------------
# Checkout & Payment Schemas
# ---------------------------------------------------------------------------


class CheckoutRequest(StrictRequestModel):
    """Checkout request accepts only an optional idempotency key; never prices or totals."""

    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=120)


class PaymentInitPayload(BaseModel):
    payment_id: uuid.UUID
    gateway_name: str
    gateway_order_id: str
    public_key_id: str
    amount: Decimal
    amount_subunits: int
    currency: str


class CheckoutResponse(BaseModel):
    order_id: uuid.UUID
    order_number: str
    status: OrderStatus
    payment_status: OrderPaymentStatus
    subtotal_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    currency: str
    payment: PaymentInitPayload
    created_at: datetime


class PaymentVerifyRequest(StrictRequestModel):
    order_id: uuid.UUID
    gateway_order_id: str = Field(..., min_length=4, max_length=100)
    gateway_payment_id: str = Field(..., min_length=4, max_length=100)
    gateway_signature: str = Field(..., min_length=8, max_length=255)
    payment_method: Optional[str] = Field(default="upi", max_length=30)


class PaymentSummaryResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    gateway_name: str
    gateway_order_id: str
    gateway_payment_id: Optional[str] = None
    refund_id: Optional[str] = None
    amount: Decimal
    currency: str
    status: PaymentStatus
    payment_method: Optional[str] = None
    is_signature_verified: bool
    failure_reason: Optional[str] = None
    verified_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Order & Invoice Schemas (Customer & Admin)
# ---------------------------------------------------------------------------


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    product_id: Optional[uuid.UUID] = None
    product_slug: Optional[str] = None
    seller_id: Optional[uuid.UUID] = None
    seller_store_name_snapshot: str = "DIGI-VERSE Official"
    seller_store_slug_snapshot: Optional[str] = None
    product_name_snapshot: str
    original_price_snapshot: Decimal
    purchase_price: Decimal
    quantity: int
    line_total: Decimal
    download_eligible: bool
    downloads_used: int = 0
    max_downloads: int = 5


class OrderResponse(BaseModel):
    id: uuid.UUID
    order_number: str
    customer_id: uuid.UUID
    subtotal_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    currency: str
    status: OrderStatus
    payment_status: OrderPaymentStatus
    download_eligible: bool
    items: list[OrderItemResponse]
    payments: list[PaymentSummaryResponse] = []
    paid_at: Optional[datetime] = None
    fulfilled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PaginatedOrderResponse(BaseModel):
    items: list[OrderResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class OrderInvoiceResponse(BaseModel):
    invoice_number: str
    order_id: uuid.UUID
    order_number: str
    issued_at: datetime
    customer_name: str
    customer_email: str
    customer_phone: Optional[str] = None
    currency: str
    subtotal_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    payment_status: OrderPaymentStatus
    gateway_payment_id: Optional[str] = None
    payment_method: Optional[str] = None
    items: list[OrderItemResponse]


class AdminOrderCustomerInfo(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    phone_number: Optional[str] = None


class DownloadRecordSummary(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    order_item_id: Optional[uuid.UUID] = None
    product_id: Optional[uuid.UUID] = None
    product_name: str
    status: DownloadStatus
    downloaded_at: datetime
    ip_address: Optional[str] = None


class AdminOrderResponse(OrderResponse):
    customer: AdminOrderCustomerInfo
    downloads: list[DownloadRecordSummary] = []


class PaginatedAdminOrderResponse(BaseModel):
    items: list[AdminOrderResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AdminOrderStatusUpdateRequest(StrictRequestModel):
    status: OrderStatus


class AdminOrderStatisticsResponse(BaseModel):
    total_orders: int
    pending_orders: int
    confirmed_orders: int
    fulfilled_orders: int
    cancelled_orders: int
    refunded_orders: int
    failed_orders: int
    paid_orders: int
    unpaid_orders: int
    total_revenue: Decimal
    total_refunded_amount: Decimal
    total_downloads: int


# ---------------------------------------------------------------------------
# Digital Delivery Schemas
# ---------------------------------------------------------------------------


class CustomerDownloadableItemResponse(BaseModel):
    order_id: uuid.UUID
    order_number: str
    order_item_id: uuid.UUID
    product_id: Optional[uuid.UUID] = None
    product_name: str
    product_slug: Optional[str] = None
    purchased_at: datetime
    download_eligible: bool
    downloads_used: int
    max_downloads: int
    remaining_downloads: int
    asset_filename: Optional[str] = None
    asset_content_type: Optional[str] = None
    asset_size_bytes: Optional[int] = None


class CustomerDownloadsOverviewResponse(BaseModel):
    eligible_items: list[CustomerDownloadableItemResponse]
    history: list[DownloadRecordSummary]


class DownloadGrantResponse(BaseModel):
    download_id: uuid.UUID
    order_id: uuid.UUID
    order_item_id: uuid.UUID
    product_id: Optional[uuid.UUID] = None
    product_name: str
    status: DownloadStatus
    download_url: str
    expires_at: datetime
    downloads_used: int
    max_downloads: int
    remaining_downloads: int
    filename: Optional[str] = None


class DownloadStatusResponse(BaseModel):
    download_id: uuid.UUID
    order_id: uuid.UUID
    order_item_id: Optional[uuid.UUID] = None
    product_id: Optional[uuid.UUID] = None
    product_name: str
    status: DownloadStatus
    downloaded_at: datetime
    downloads_used: int
    max_downloads: int
    remaining_downloads: int
