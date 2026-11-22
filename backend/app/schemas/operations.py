import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    AccountStatus,
    ActivityType,
    AdDisplayPosition,
    CampaignStatus,
    DeliveryStatus,
    MessageChannel,
)
from app.schemas.auth import StrictRequestModel
from app.schemas.catalog import validate_safe_url

SETTING_KEY_REGEX = re.compile(r"^[a-z0-9_.]+$")
FORBIDDEN_SECRET_KEY_FRAGMENTS = (
    "secret",
    "password",
    "private_key",
    "api_key",
    "access_token",
    "webhook_secret",
    "service_role",
)
PROTECTED_SYSTEM_SETTING_KEYS = {"system.initial_admin_provisioned"}


def validate_safe_setting_key(key: str) -> str:
    cleaned = key.strip().lower()
    if not SETTING_KEY_REGEX.match(cleaned):
        raise ValueError("Setting key must use lowercase letters, numbers, dots, or underscores.")
    if cleaned in PROTECTED_SYSTEM_SETTING_KEYS:
        raise ValueError(f"Setting key '{cleaned}' is a protected internal system key.")
    for frag in FORBIDDEN_SECRET_KEY_FRAGMENTS:
        if frag in cleaned:
            raise ValueError(
                f"Store settings cannot store secrets or credentials ('{frag}'). Use environment variables."
            )
    return cleaned


# ---------------------------------------------------------------------------
# 1. ADVANCED DASHBOARD & ANALYTICS SCHEMAS
# ---------------------------------------------------------------------------


class TimeSeriesPoint(BaseModel):
    period: str
    revenue: Decimal
    order_count: int
    new_customers: int = 0


class BestSellingProductMetric(BaseModel):
    product_id: Optional[uuid.UUID] = None
    product_name: str
    product_slug: Optional[str] = None
    units_sold: int
    total_revenue: Decimal


class TopCategoryMetric(BaseModel):
    category_id: uuid.UUID
    category_name: str
    category_slug: str
    units_sold: int
    total_revenue: Decimal


class MostDownloadedProductMetric(BaseModel):
    product_id: Optional[uuid.UUID] = None
    product_name: str
    product_slug: Optional[str] = None
    download_count: int


class CustomerActivityItemResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str
    customer_email: str
    activity_type: ActivityType
    product_id: Optional[uuid.UUID] = None
    category_id: Optional[uuid.UUID] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime


class DashboardAnalyticsResponse(BaseModel):
    date_from: datetime
    date_to: datetime
    daily_sales: list[TimeSeriesPoint]
    weekly_sales: list[TimeSeriesPoint]
    monthly_sales: list[TimeSeriesPoint]
    best_selling_products: list[BestSellingProductMetric]
    top_categories: list[TopCategoryMetric]
    most_downloaded_products: list[MostDownloadedProductMetric]
    recent_customer_activity: list[CustomerActivityItemResponse]


# ---------------------------------------------------------------------------
# 2. ADMIN CUSTOMER MANAGEMENT SCHEMAS
# ---------------------------------------------------------------------------


class AdminCustomerSummaryResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    phone_number: Optional[str] = None
    is_email_verified: bool
    is_phone_verified: bool
    account_status: AccountStatus
    email_marketing_consent: bool
    whatsapp_marketing_consent: bool
    order_count: int = 0
    total_spent: Decimal = Decimal("0.00")
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PaginatedAdminCustomerResponse(BaseModel):
    items: list[AdminCustomerSummaryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AdminCustomerStatusUpdateRequest(StrictRequestModel):
    account_status: AccountStatus


# ---------------------------------------------------------------------------
# 3. PROMOTIONAL BANNERS SCHEMAS
# ---------------------------------------------------------------------------


class BannerCreateRequest(StrictRequestModel):
    heading: str = Field(..., min_length=2, max_length=200)
    subtitle: Optional[str] = Field(default=None, max_length=300)
    promotional_text: Optional[str] = Field(default=None, max_length=2000)
    image_url: str = Field(..., min_length=3, max_length=1024)
    cta_text: Optional[str] = Field(default=None, max_length=60)
    cta_destination: Optional[str] = Field(default=None, max_length=1024)
    display_priority: int = Field(default=0, ge=0, le=1000)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active: bool = True

    @field_validator("image_url", "cta_destination")
    @classmethod
    def _validate_urls(cls, v: Optional[str]) -> Optional[str]:
        return validate_safe_url(v)

    @model_validator(mode="after")
    def _check_dates(self) -> "BannerCreateRequest":
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("Banner end date must be after start date.")
        return self


class BannerUpdateRequest(StrictRequestModel):
    heading: Optional[str] = Field(default=None, min_length=2, max_length=200)
    subtitle: Optional[str] = Field(default=None, max_length=300)
    promotional_text: Optional[str] = Field(default=None, max_length=2000)
    image_url: Optional[str] = Field(default=None, min_length=3, max_length=1024)
    cta_text: Optional[str] = Field(default=None, max_length=60)
    cta_destination: Optional[str] = Field(default=None, max_length=1024)
    display_priority: Optional[int] = Field(default=None, ge=0, le=1000)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active: Optional[bool] = None

    @field_validator("image_url", "cta_destination")
    @classmethod
    def _validate_urls(cls, v: Optional[str]) -> Optional[str]:
        return validate_safe_url(v)


class BannerResponse(BaseModel):
    id: uuid.UUID
    heading: str
    subtitle: Optional[str] = None
    promotional_text: Optional[str] = None
    image_url: str
    cta_text: Optional[str] = None
    cta_destination: Optional[str] = None
    display_priority: int
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# 4. ADVERTISEMENT VIDEOS SCHEMAS
# ---------------------------------------------------------------------------


class AdVideoCreateRequest(StrictRequestModel):
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    video_url: str = Field(..., min_length=3, max_length=1024)
    thumbnail_url: Optional[str] = Field(default=None, max_length=1024)
    destination_url: Optional[str] = Field(default=None, max_length=1024)
    display_position: AdDisplayPosition = AdDisplayPosition.HOME_SECTION
    display_priority: int = Field(default=0, ge=0, le=1000)
    is_active: bool = True

    @field_validator("video_url", "thumbnail_url", "destination_url")
    @classmethod
    def _validate_urls(cls, v: Optional[str]) -> Optional[str]:
        return validate_safe_url(v)


class AdVideoUpdateRequest(StrictRequestModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    video_url: Optional[str] = Field(default=None, min_length=3, max_length=1024)
    thumbnail_url: Optional[str] = Field(default=None, max_length=1024)
    destination_url: Optional[str] = Field(default=None, max_length=1024)
    display_position: Optional[AdDisplayPosition] = None
    display_priority: Optional[int] = Field(default=None, ge=0, le=1000)
    is_active: Optional[bool] = None

    @field_validator("video_url", "thumbnail_url", "destination_url")
    @classmethod
    def _validate_urls(cls, v: Optional[str]) -> Optional[str]:
        return validate_safe_url(v)


class AdVideoResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str] = None
    video_url: str
    thumbnail_url: Optional[str] = None
    destination_url: Optional[str] = None
    display_position: AdDisplayPosition
    display_priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# 5. MARKETING AUTOMATION: TEMPLATES & CAMPAIGNS SCHEMAS
# ---------------------------------------------------------------------------


class MessageTemplateCreateRequest(StrictRequestModel):
    name: str = Field(..., min_length=2, max_length=150)
    channel: MessageChannel
    subject: Optional[str] = Field(default=None, max_length=255)
    content: str = Field(..., min_length=2, max_length=20000)

    @model_validator(mode="after")
    def _validate_channel_subject(self) -> "MessageTemplateCreateRequest":
        if self.channel == MessageChannel.EMAIL and (not self.subject or not self.subject.strip()):
            raise ValueError("Email templates require a non-empty subject.")
        return self


class MessageTemplateUpdateRequest(StrictRequestModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    subject: Optional[str] = Field(default=None, max_length=255)
    content: Optional[str] = Field(default=None, min_length=2, max_length=20000)


class MessageTemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    channel: MessageChannel
    subject: Optional[str] = None
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmailCampaignCreateRequest(StrictRequestModel):
    name: str = Field(..., min_length=2, max_length=150)
    subject: str = Field(..., min_length=2, max_length=255)
    content: str = Field(..., min_length=2, max_length=50000)
    template_id: Optional[uuid.UUID] = None
    audience_criteria: Optional[dict[str, Any]] = None


class WhatsAppCampaignCreateRequest(StrictRequestModel):
    name: str = Field(..., min_length=2, max_length=150)
    content: str = Field(..., min_length=2, max_length=10000)
    approved_template_name: str = Field(..., min_length=2, max_length=150)
    template_id: Optional[uuid.UUID] = None
    audience_criteria: Optional[dict[str, Any]] = None


class CampaignScheduleRequest(StrictRequestModel):
    scheduled_for: Optional[datetime] = None


class CampaignRecipientSummary(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    customer_email: Optional[str] = None
    delivery_status: DeliveryStatus
    provider_message_id: Optional[str] = None
    attempt_count: int = 0
    max_attempts: int = 5
    next_retry_at: Optional[datetime] = None
    error_code: Optional[str] = None
    is_retryable_error: Optional[bool] = None
    failure_reason: Optional[str] = None
    sent_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    bounced_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None


class CampaignStatsMixin(BaseModel):
    recipient_count: int = 0
    queued_count: int = 0
    processing_count: int = 0
    retrying_count: int = 0
    accepted_count: int = 0
    delivered_count: int = 0
    read_count: int = 0
    bounced_count: int = 0
    suppressed_count: int = 0
    skipped_count: int = 0
    unresolved_count: int = 0
    sent_count: int = 0
    failed_count: int = 0


class EmailCampaignResponse(CampaignStatsMixin):
    id: uuid.UUID
    name: str
    subject: str
    content: str
    template_id: Optional[uuid.UUID] = None
    audience_criteria: Optional[dict[str, Any]] = None
    status: CampaignStatus
    scheduled_for: Optional[datetime] = None
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class WhatsAppCampaignResponse(CampaignStatsMixin):
    id: uuid.UUID
    name: str
    content: str
    approved_template_name: str
    template_id: Optional[uuid.UUID] = None
    audience_criteria: Optional[dict[str, Any]] = None
    status: CampaignStatus
    scheduled_for: Optional[datetime] = None
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class CampaignDetailResponse(CampaignStatsMixin):
    id: uuid.UUID
    channel: MessageChannel
    name: str
    subject: Optional[str] = None
    content: str
    approved_template_name: Optional[str] = None
    template_id: Optional[uuid.UUID] = None
    audience_criteria: Optional[dict[str, Any]] = None
    status: CampaignStatus
    scheduled_for: Optional[datetime] = None
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    last_error: Optional[str] = None
    failure_summary: dict[str, int] = Field(default_factory=dict)
    recipients: list[CampaignRecipientSummary] = Field(default_factory=list)


class CampaignLaunchResponse(BaseModel):
    campaign_id: uuid.UUID
    channel: MessageChannel
    status: CampaignStatus
    targeted_recipients: int
    sent_count: int
    failed_count: int
    accepted_count: int = 0
    retrying_count: int = 0
    skipped_count: int = 0
    unresolved_count: int = 0
    completed_at: Optional[datetime] = None


class WorkerHeartbeatResponse(BaseModel):
    worker_id: str
    hostname: str
    pid: int
    status: str
    started_at: datetime
    last_heartbeat_at: datetime
    processed_jobs_count: int


class MarketingWorkerStatusResponse(BaseModel):
    queued_jobs: int
    processing_jobs: int
    retrying_jobs: int
    scheduled_campaigns: int
    workers: list[WorkerHeartbeatResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 6. STORE SETTINGS & AUDIT LOG SCHEMAS
# ---------------------------------------------------------------------------


class StoreSettingUpsertRequest(StrictRequestModel):
    key: str = Field(..., min_length=2, max_length=100)
    value: Any

    @field_validator("key")
    @classmethod
    def _validate_key(cls, v: str) -> str:
        return validate_safe_setting_key(v)


class StoreSettingsBatchUpdateRequest(StrictRequestModel):
    settings: dict[str, Any]

    @field_validator("settings")
    @classmethod
    def _validate_batch_keys(cls, v: dict[str, Any]) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        for k, val in v.items():
            safe_k = validate_safe_setting_key(k)
            cleaned[safe_k] = val
        return cleaned


class StoreSettingResponse(BaseModel):
    id: uuid.UUID
    key: str
    value: Any
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogEntryResponse(BaseModel):
    id: uuid.UUID
    admin_id: Optional[uuid.UUID] = None
    admin_username: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime


class PaginatedAuditLogResponse(BaseModel):
    items: list[AuditLogEntryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
