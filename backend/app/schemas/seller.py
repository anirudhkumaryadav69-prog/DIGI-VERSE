"""Pydantic schemas for multi-vendor seller onboarding, storefronts, dashboards, and moderation."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    OrderPaymentStatus,
    OrderStatus,
    ProductApprovalStatus,
    SellerApplicationStatus,
)
from app.schemas.auth import StrictRequestModel, normalize_and_validate_email
from app.schemas.catalog import (
    PaginatedProductPublicResponse,
    validate_safe_url,
    validate_slug_format,
)


class SellerApplicationCreateRequest(StrictRequestModel):
    store_name: str = Field(..., min_length=2, max_length=150)
    store_slug: Optional[str] = Field(default=None, max_length=160)
    seller_display_name: str = Field(..., min_length=2, max_length=150)
    store_description: Optional[str] = Field(default=None, max_length=5000)
    application_description: str = Field(..., min_length=10, max_length=5000)
    logo_url: Optional[str] = Field(default=None, max_length=1024)
    banner_url: Optional[str] = Field(default=None, max_length=1024)
    contact_email: str = Field(..., max_length=255)
    contact_info: Optional[str] = Field(default=None, max_length=255)
    country: str = Field(..., min_length=2, max_length=100)
    business_type: str = Field(..., min_length=2, max_length=80)
    product_categories: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("store_slug")
    @classmethod
    def _check_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        return validate_slug_format(v)

    @field_validator("logo_url", "banner_url")
    @classmethod
    def _check_urls(cls, v: Optional[str]) -> Optional[str]:
        return validate_safe_url(v)

    @field_validator("contact_email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        return normalize_and_validate_email(v)

    @field_validator("product_categories")
    @classmethod
    def _clean_categories(cls, v: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in v:
            s = (item or "").strip()
            if s and s not in cleaned:
                cleaned.append(s[:80])
        return cleaned


class SellerProfileUpdateRequest(StrictRequestModel):
    store_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    seller_display_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    store_description: Optional[str] = Field(default=None, max_length=5000)
    logo_url: Optional[str] = Field(default=None, max_length=1024)
    banner_url: Optional[str] = Field(default=None, max_length=1024)
    contact_email: Optional[str] = Field(default=None, max_length=255)
    contact_info: Optional[str] = Field(default=None, max_length=255)
    country: Optional[str] = Field(default=None, min_length=2, max_length=100)
    business_type: Optional[str] = Field(default=None, min_length=2, max_length=80)
    product_categories: Optional[list[str]] = Field(default=None, max_length=20)

    @field_validator("logo_url", "banner_url")
    @classmethod
    def _check_urls(cls, v: Optional[str]) -> Optional[str]:
        return validate_safe_url(v)

    @field_validator("contact_email")
    @classmethod
    def _check_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return normalize_and_validate_email(v)


class SellerProfileResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    store_name: str
    store_slug: str
    seller_display_name: str
    store_description: Optional[str] = None
    application_description: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    contact_email: str
    contact_info: Optional[str] = None
    country: str
    business_type: str
    product_categories: list[str] = []
    application_status: SellerApplicationStatus
    rejection_reason: Optional[str] = None
    suspension_reason: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    suspended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SellerPublicProfileResponse(BaseModel):
    id: uuid.UUID
    store_name: str
    store_slug: str
    seller_display_name: str
    store_description: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    country: str
    business_type: str
    product_categories: list[str] = []
    published_product_count: int = 0
    created_at: datetime


class SellerPublicStorefrontResponse(BaseModel):
    seller: SellerPublicProfileResponse
    categories: list[dict]
    products: PaginatedProductPublicResponse


class PaginatedSellerDirectoryResponse(BaseModel):
    items: list[SellerPublicProfileResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AdminSellerSummaryResponse(SellerProfileResponse):
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    product_count: int = 0
    published_product_count: int = 0


class PaginatedAdminSellerResponse(BaseModel):
    items: list[AdminSellerSummaryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AdminSellerReviewRequest(StrictRequestModel):
    action: Literal["approve", "reject", "suspend", "reinstate"]
    reason: Optional[str] = Field(default=None, max_length=2000)


class SellerOrderItemResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    product_id: Optional[uuid.UUID] = None
    product_name_snapshot: str
    original_price_snapshot: Decimal
    purchase_price: Decimal
    quantity: int
    line_total: Decimal
    seller_store_name_snapshot: str
    seller_store_slug_snapshot: Optional[str] = None
    downloads_used: int = 0
    max_downloads: int = 5


class SellerOrderResponse(BaseModel):
    order_id: uuid.UUID
    order_number: str
    created_at: datetime
    paid_at: Optional[datetime] = None
    fulfilled_at: Optional[datetime] = None
    status: OrderStatus
    payment_status: OrderPaymentStatus
    currency: str
    seller_items_subtotal: Decimal
    seller_units_count: int
    download_fulfilment_status: str
    items: list[SellerOrderItemResponse]


class PaginatedSellerOrderResponse(BaseModel):
    items: list[SellerOrderResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SellerProductPerformanceItem(BaseModel):
    product_id: uuid.UUID
    name: str
    slug: str
    approval_status: ProductApprovalStatus
    is_active: bool
    units_sold: int
    gross_sales: Decimal
    downloads_count: int


class SellerOverviewResponse(BaseModel):
    store_name: str
    store_slug: str
    application_status: SellerApplicationStatus
    total_products: int
    published_products: int
    draft_products: int
    pending_review_products: int
    rejected_products: int
    archived_products: int
    total_orders: int
    paid_orders: int
    total_units_sold: int
    gross_product_sales: Decimal
    currency: str = "INR"
    recent_orders: list[SellerOrderResponse] = []
    top_products: list[SellerProductPerformanceItem] = []


class SellerAnalyticsResponse(BaseModel):
    currency: str = "INR"
    total_orders: int
    total_units_sold: int
    gross_product_sales: Decimal
    total_downloads: int
    product_breakdown: list[SellerProductPerformanceItem] = []
    daily_sales: list[dict] = []
