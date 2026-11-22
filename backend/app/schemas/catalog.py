import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import ProductApprovalStatus
from app.schemas.auth import StrictRequestModel

SLUG_REGEX = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def slugify(text: str) -> str:
    """Convert an arbitrary name into a URL-friendly kebab-case slug."""
    cleaned = text.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    if not cleaned or not SLUG_REGEX.match(cleaned):
        raise ValueError("Unable to generate a valid URL slug from the provided name.")
    return cleaned


def validate_slug_format(value: str) -> str:
    cleaned = value.strip().lower()
    if not SLUG_REGEX.match(cleaned):
        raise ValueError("Slug must be lowercase kebab-case (letters, numbers, and single hyphens).")
    return cleaned


def validate_safe_url(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    lower = cleaned.lower()
    if lower.startswith(("javascript:", "vbscript:", "data:")):
        raise ValueError("URL scheme is not permitted.")
    if not (cleaned.startswith("/") or lower.startswith(("https://", "http://"))):
        raise ValueError("URL must be a relative path starting with '/' or an HTTP/HTTPS URL.")
    return cleaned


# ---------------------------------------------------------------------------
# Category Schemas
# ---------------------------------------------------------------------------


class CategoryCreateRequest(StrictRequestModel):
    name: str = Field(..., min_length=2, max_length=120)
    slug: Optional[str] = Field(default=None, max_length=140)
    description: Optional[str] = Field(default=None, max_length=5000)
    image_url: Optional[str] = Field(default=None, max_length=1024)
    is_active: bool = True

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        return validate_slug_format(v)

    @field_validator("image_url")
    @classmethod
    def _check_image_url(cls, v: Optional[str]) -> Optional[str]:
        return validate_safe_url(v)


class CategoryUpdateRequest(StrictRequestModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    slug: Optional[str] = Field(default=None, max_length=140)
    description: Optional[str] = Field(default=None, max_length=5000)
    image_url: Optional[str] = Field(default=None, max_length=1024)
    is_active: Optional[bool] = None

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        return validate_slug_format(v)

    @field_validator("image_url")
    @classmethod
    def _check_image_url(cls, v: Optional[str]) -> Optional[str]:
        return validate_safe_url(v)


class CategoryAdminResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool
    product_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CategoryPublicResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    product_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class PaginatedCategoryAdminResponse(BaseModel):
    items: list[CategoryAdminResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedCategoryPublicResponse(BaseModel):
    items: list[CategoryPublicResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Product Image & Sale / Discount Schemas
# ---------------------------------------------------------------------------


class ProductImageResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    image_url: str
    display_order: int
    is_primary: bool

    model_config = ConfigDict(from_attributes=True)


class ProductImageUpdateRequest(StrictRequestModel):
    display_order: Optional[int] = Field(default=None, ge=0, le=1000)
    is_primary: Optional[bool] = None


class SaleCreateRequest(StrictRequestModel):
    discounted_price: Decimal = Field(..., ge=Decimal("0.00"), max_digits=12, decimal_places=2)
    starts_at: datetime
    expires_at: datetime
    is_active: bool = True

    @model_validator(mode="after")
    def _validate_dates(self) -> "SaleCreateRequest":
        if self.expires_at <= self.starts_at:
            raise ValueError("Discount expiry date must be after the start date.")
        return self


class SaleUpdateRequest(StrictRequestModel):
    discounted_price: Optional[Decimal] = Field(
        default=None, ge=Decimal("0.00"), max_digits=12, decimal_places=2
    )
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None


class SaleAdminResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    original_price_snapshot: Decimal
    discounted_price: Decimal
    discount_amount: Decimal
    discount_percentage: Decimal
    starts_at: datetime
    expires_at: datetime
    is_active: bool
    is_currently_live: bool
    created_at: datetime


class ActiveDiscountPublicResponse(BaseModel):
    sale_id: uuid.UUID
    original_price: Decimal
    discounted_price: Decimal
    discount_amount: Decimal
    discount_percentage: Decimal
    starts_at: datetime
    expires_at: datetime


# ---------------------------------------------------------------------------
# Product Schemas (Strict separation between Admin and Public responses)
# ---------------------------------------------------------------------------


class ProductCreateRequest(StrictRequestModel):
    name: str = Field(..., min_length=2, max_length=200)
    slug: Optional[str] = Field(default=None, max_length=220)
    category_id: uuid.UUID
    image_url: Optional[str] = Field(default=None, max_length=1024)
    short_description: Optional[str] = Field(default=None, max_length=500)
    main_description: Optional[str] = Field(default=None, max_length=20000)
    detailed_description: Optional[str] = Field(default=None, max_length=50000)
    original_price: Decimal = Field(..., ge=Decimal("0.00"), max_digits=12, decimal_places=2)
    product_type: Optional[str] = Field(default=None, max_length=80)
    metadata: Optional[dict[str, Any]] = None
    is_active: bool = True
    private_download_url: Optional[str] = Field(default=None, max_length=2048)

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        return validate_slug_format(v)

    @field_validator("image_url")
    @classmethod
    def _check_image_url(cls, v: Optional[str]) -> Optional[str]:
        return validate_safe_url(v)


class ProductUpdateRequest(StrictRequestModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    slug: Optional[str] = Field(default=None, max_length=220)
    category_id: Optional[uuid.UUID] = None
    image_url: Optional[str] = Field(default=None, max_length=1024)
    short_description: Optional[str] = Field(default=None, max_length=500)
    main_description: Optional[str] = Field(default=None, max_length=20000)
    detailed_description: Optional[str] = Field(default=None, max_length=50000)
    original_price: Optional[Decimal] = Field(
        default=None, ge=Decimal("0.00"), max_digits=12, decimal_places=2
    )
    product_type: Optional[str] = Field(default=None, max_length=80)
    metadata: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None
    private_download_url: Optional[str] = Field(default=None, max_length=2048)

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        return validate_slug_format(v)

    @field_validator("image_url")
    @classmethod
    def _check_image_url(cls, v: Optional[str]) -> Optional[str]:
        return validate_safe_url(v)


class ProductStatusUpdateRequest(StrictRequestModel):
    is_active: bool


class CategorySummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ProductAssetAdminResponse(BaseModel):
    """Safe digital asset metadata for administrators (never exposes storage keys or paths)."""

    has_asset: bool = False
    filename: Optional[str] = None
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    sha256: Optional[str] = None
    storage_backend: Optional[str] = None
    uploaded_at: Optional[datetime] = None


class SellerPublicBadge(BaseModel):
    """Lightweight public storefront attribution attached to seller-owned products."""

    id: uuid.UUID
    store_name: str
    store_slug: str
    seller_display_name: str
    logo_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProductAdminResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    category_id: uuid.UUID
    category: Optional[CategorySummary] = None
    seller_id: Optional[uuid.UUID] = None
    seller: Optional[SellerPublicBadge] = None
    approval_status: ProductApprovalStatus = ProductApprovalStatus.PUBLISHED
    rejection_reason: Optional[str] = None
    submitted_for_review_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    image_url: Optional[str] = None
    short_description: Optional[str] = None
    main_description: Optional[str] = None
    detailed_description: Optional[str] = None
    original_price: Decimal
    effective_price: Decimal
    is_on_sale: bool
    is_active: bool
    product_type: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    private_download_url: Optional[str] = None
    asset: Optional[ProductAssetAdminResponse] = None
    images: list[ProductImageResponse] = []
    sales: list[SaleAdminResponse] = []
    active_discount: Optional[ActiveDiscountPublicResponse] = None
    created_at: datetime
    updated_at: datetime


class AdminProductModerationRequest(StrictRequestModel):
    action: Literal["approve", "reject", "unpublish", "restore"]
    reason: Optional[str] = Field(default=None, max_length=2000)


class SellerProductCreateRequest(StrictRequestModel):
    """Seller product creation request. Ownership is always derived from backend SellerProfile."""

    name: str = Field(..., min_length=2, max_length=200)
    slug: Optional[str] = Field(default=None, max_length=220)
    category_id: uuid.UUID
    image_url: Optional[str] = Field(default=None, max_length=1024)
    short_description: Optional[str] = Field(default=None, max_length=500)
    main_description: Optional[str] = Field(default=None, max_length=20000)
    detailed_description: Optional[str] = Field(default=None, max_length=50000)
    original_price: Decimal = Field(..., ge=Decimal("0.00"), max_digits=12, decimal_places=2)
    product_type: Optional[str] = Field(default=None, max_length=80)
    metadata: Optional[dict[str, Any]] = None
    submit_for_review: bool = False

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        return validate_slug_format(v)

    @field_validator("image_url")
    @classmethod
    def _check_image_url(cls, v: Optional[str]) -> Optional[str]:
        return validate_safe_url(v)


class SellerProductUpdateRequest(StrictRequestModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    slug: Optional[str] = Field(default=None, max_length=220)
    category_id: Optional[uuid.UUID] = None
    image_url: Optional[str] = Field(default=None, max_length=1024)
    short_description: Optional[str] = Field(default=None, max_length=500)
    main_description: Optional[str] = Field(default=None, max_length=20000)
    detailed_description: Optional[str] = Field(default=None, max_length=50000)
    original_price: Optional[Decimal] = Field(
        default=None, ge=Decimal("0.00"), max_digits=12, decimal_places=2
    )
    product_type: Optional[str] = Field(default=None, max_length=80)
    metadata: Optional[dict[str, Any]] = None

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        return validate_slug_format(v)

    @field_validator("image_url")
    @classmethod
    def _check_image_url(cls, v: Optional[str]) -> Optional[str]:
        return validate_safe_url(v)


class SellerProductStatusActionRequest(StrictRequestModel):
    action: Literal["save_draft", "submit_for_review", "publish", "unpublish", "archive"]


class SellerProductResponse(ProductAdminResponse):
    """Seller-owned product management representation (excludes other sellers & raw keys)."""

    private_download_url: Optional[str] = None


class PaginatedSellerProductResponse(BaseModel):
    items: list[SellerProductResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PublicCategorySummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str

    model_config = ConfigDict(from_attributes=True)


class ProductPublicResponse(BaseModel):
    """Customer-facing product representation. Never exposes private_download_url or admin metadata."""

    id: uuid.UUID
    name: str
    slug: str
    category: PublicCategorySummary
    seller: Optional[SellerPublicBadge] = None
    is_platform_product: bool = True
    image_url: Optional[str] = None
    images: list[ProductImageResponse] = []
    short_description: Optional[str] = None
    main_description: Optional[str] = None
    detailed_description: Optional[str] = None
    product_type: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    original_price: Decimal
    effective_price: Decimal
    is_on_sale: bool
    active_discount: Optional[ActiveDiscountPublicResponse] = None
    is_available: bool = True
    created_at: datetime


class PaginatedProductAdminResponse(BaseModel):
    items: list[ProductAdminResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedProductPublicResponse(BaseModel):
    items: list[ProductPublicResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
