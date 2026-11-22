"""Multi-vendor seller profile model bound 1:1 to an authenticated Customer identity."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import SellerApplicationStatus
from app.models.mixins import TimestampMixin, enum_col, uuid_pk

if TYPE_CHECKING:
    from app.models.admin import Admin
    from app.models.catalog import Product
    from app.models.customer import Customer


class SellerProfile(TimestampMixin, Base):
    """Storefront & merchant identity linked to a single verified Customer account."""

    __tablename__ = "seller_profiles"

    id: Mapped[uuid.UUID] = uuid_pk()
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    store_name: Mapped[str] = mapped_column(String(150), nullable=False)
    store_slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    seller_display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    store_description: Mapped[Optional[str]] = mapped_column(Text)
    application_description: Mapped[Optional[str]] = mapped_column(Text)
    logo_url: Mapped[Optional[str]] = mapped_column(String(1024))
    banner_url: Mapped[Optional[str]] = mapped_column(String(1024))
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_info: Mapped[Optional[str]] = mapped_column(String(255))
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    business_type: Mapped[str] = mapped_column(String(80), nullable=False)
    product_categories: Mapped[Optional[list[str]]] = mapped_column(JSONB)

    application_status: Mapped[SellerApplicationStatus] = mapped_column(
        enum_col(SellerApplicationStatus, "seller_application_status"),
        nullable=False,
        default=SellerApplicationStatus.PENDING,
        server_default=SellerApplicationStatus.PENDING.value,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)
    suspension_reason: Mapped[Optional[str]] = mapped_column(Text)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    approved_by_admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("admins.id", ondelete="SET NULL"),
    )
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    customer: Mapped["Customer"] = relationship(back_populates="seller_profile")
    approved_by_admin: Mapped[Optional["Admin"]] = relationship()
    products: Mapped[list["Product"]] = relationship(back_populates="seller")

    __table_args__ = (
        CheckConstraint("store_slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="store_slug_format"),
        Index("ix_seller_profiles_status", "application_status"),
        Index("ix_seller_profiles_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<SellerProfile {self.store_slug} ({self.application_status.value})>"
