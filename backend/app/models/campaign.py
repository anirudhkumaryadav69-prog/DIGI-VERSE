import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import CampaignStatus, DeliveryStatus, MessageChannel
from app.models.mixins import TimestampMixin, created_at_col, enum_col, updated_at_col, uuid_pk

if TYPE_CHECKING:
    from app.models.customer import Customer


class MessageTemplate(TimestampMixin, Base):
    __tablename__ = "message_templates"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    channel: Mapped[MessageChannel] = mapped_column(enum_col(MessageChannel, "message_channel"), nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("name", "channel"),
        CheckConstraint("channel <> 'email' OR subject IS NOT NULL", name="email_requires_subject"),
    )


class EmailCampaign(Base):
    __tablename__ = "email_campaigns"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("message_templates.id", ondelete="SET NULL")
    )
    audience_criteria: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    status: Mapped[CampaignStatus] = mapped_column(
        enum_col(CampaignStatus, "email_campaign_status"),
        nullable=False,
        default=CampaignStatus.DRAFT,
        server_default=CampaignStatus.DRAFT.value,
    )
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[Optional[str]] = mapped_column(String(120))
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    template: Mapped[Optional[MessageTemplate]] = relationship()
    recipients: Mapped[list["CampaignRecipient"]] = relationship(
        back_populates="email_campaign", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        Index("ix_email_campaigns_status_scheduled", "status", "scheduled_for"),
    )


class WhatsAppCampaign(Base):
    __tablename__ = "whatsapp_campaigns"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("message_templates.id", ondelete="SET NULL")
    )
    # Name of the template approved by Meta for WhatsApp Business Cloud API.
    approved_template_name: Mapped[str] = mapped_column(String(150), nullable=False)
    audience_criteria: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    status: Mapped[CampaignStatus] = mapped_column(
        enum_col(CampaignStatus, "whatsapp_campaign_status"),
        nullable=False,
        default=CampaignStatus.DRAFT,
        server_default=CampaignStatus.DRAFT.value,
    )
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[Optional[str]] = mapped_column(String(120))
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    template: Mapped[Optional[MessageTemplate]] = relationship()
    recipients: Mapped[list["CampaignRecipient"]] = relationship(
        back_populates="whatsapp_campaign", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        Index("ix_whatsapp_campaigns_status_scheduled", "status", "scheduled_for"),
    )


class CampaignRecipient(Base):
    """Per-customer delivery job and state record for one email OR WhatsApp campaign.

    Consent is enforced in PostgreSQL by the `trg_campaign_recipient_consent` trigger
    (see the initial migration): inserts are rejected unless the customer is active and
    has opted in to the campaign's channel.
    """

    __tablename__ = "campaign_recipients"

    id: Mapped[uuid.UUID] = uuid_pk()
    channel: Mapped[MessageChannel] = mapped_column(
        enum_col(MessageChannel, "recipient_channel"), nullable=False
    )
    email_campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("email_campaigns.id", ondelete="CASCADE")
    )
    whatsapp_campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("whatsapp_campaigns.id", ondelete="CASCADE")
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        enum_col(DeliveryStatus, "delivery_status"),
        nullable=False,
        default=DeliveryStatus.QUEUED,
        server_default=DeliveryStatus.QUEUED.value,
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(120), unique=True)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(150), unique=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default=text("5"))
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[Optional[str]] = mapped_column(String(120))
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[Optional[str]] = mapped_column(String(80))
    is_retryable_error: Mapped[Optional[bool]] = mapped_column(Boolean)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)
    provider_response_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    bounced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = updated_at_col()

    customer: Mapped["Customer"] = relationship(back_populates="campaign_recipients")
    email_campaign: Mapped[Optional[EmailCampaign]] = relationship(back_populates="recipients")
    whatsapp_campaign: Mapped[Optional[WhatsAppCampaign]] = relationship(back_populates="recipients")

    __table_args__ = (
        CheckConstraint(
            "(channel = 'email' AND email_campaign_id IS NOT NULL AND whatsapp_campaign_id IS NULL) OR "
            "(channel = 'whatsapp' AND whatsapp_campaign_id IS NOT NULL AND email_campaign_id IS NULL)",
            name="exactly_one_campaign_matching_channel",
        ),
        CheckConstraint("attempt_count >= 0", name="attempt_count_non_negative"),
        CheckConstraint("max_attempts >= 1", name="max_attempts_positive"),
        UniqueConstraint("email_campaign_id", "customer_id"),
        UniqueConstraint("whatsapp_campaign_id", "customer_id"),
        Index("ix_campaign_recipients_delivery_status", "delivery_status"),
        Index(
            "ix_campaign_recipients_worker_poll",
            "delivery_status",
            "next_retry_at",
            "locked_at",
        ),
    )


class MarketingWebhookEvent(Base):
    """Persistent idempotency ledger of verified email & WhatsApp webhook events."""

    __tablename__ = "marketing_webhook_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    event_id: Mapped[str] = mapped_column(String(180), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(150), index=True)
    campaign_recipient_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("campaign_recipients.id", ondelete="SET NULL"), index=True
    )
    processing_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="processed", server_default=text("'processed'")
    )
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    received_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_marketing_webhook_provider_event_id"),
        Index("ix_marketing_webhook_events_received", "received_at"),
    )


class WorkerHeartbeat(Base):
    """Liveness heartbeat ledger for persistent background campaign workers."""

    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    hostname: Mapped[str] = mapped_column(String(150), nullable=False)
    pid: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'running'"))
    started_at: Mapped[datetime] = created_at_col()
    last_heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_jobs_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB)
