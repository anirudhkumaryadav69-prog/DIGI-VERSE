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
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AccountStatus, ActivityType, LoginStatus, SellerApplicationStatus
from app.models.mixins import TimestampMixin, created_at_col, enum_col, uuid_pk

if TYPE_CHECKING:
    from app.models.auth import AuthSession, PasswordResetToken, PhoneOTPChallenge
    from app.models.campaign import CampaignRecipient
    from app.models.catalog import Category, Product
    from app.models.order import DownloadRecord, Order, Payment
    from app.models.seller import SellerProfile
    from app.models.shopping import Cart, Wishlist


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = uuid_pk()
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), unique=True)
    pending_phone_number: Mapped[Optional[str]] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_phone_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    account_status: Mapped[AccountStatus] = mapped_column(
        enum_col(AccountStatus, "account_status"),
        nullable=False,
        default=AccountStatus.ACTIVE,
        server_default=AccountStatus.ACTIVE.value,
    )
    email_marketing_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    whatsapp_marketing_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Personal/engagement data is removed with the customer.
    wishlist_items: Mapped[list["Wishlist"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", passive_deletes=True
    )
    cart: Mapped[Optional["Cart"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )
    activities: Mapped[list["CustomerActivity"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", passive_deletes=True
    )
    login_history: Mapped[list["LoginHistory"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", passive_deletes=True
    )
    campaign_recipients: Mapped[list["CampaignRecipient"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", passive_deletes=True
    )
    sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", passive_deletes=True
    )
    otp_challenges: Mapped[list["PhoneOTPChallenge"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", passive_deletes=True
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", passive_deletes=True
    )
    # Financial records are retained (FK RESTRICT): no ORM delete cascade.
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
    payments: Mapped[list["Payment"]] = relationship(back_populates="customer")
    downloads: Mapped[list["DownloadRecord"]] = relationship(back_populates="customer")
    seller_profile: Mapped[Optional["SellerProfile"]] = relationship(
        back_populates="customer",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            "phone_number IS NULL OR phone_number ~ '^\\+[1-9][0-9]{7,14}$'", name="phone_e164"
        ),
        CheckConstraint(
            "pending_phone_number IS NULL OR pending_phone_number ~ '^\\+[1-9][0-9]{7,14}$'",
            name="pending_phone_e164",
        ),
        CheckConstraint(
            "whatsapp_marketing_consent = false OR phone_number IS NOT NULL",
            name="whatsapp_consent_requires_phone",
        ),
        CheckConstraint("failed_login_attempts >= 0", name="failed_attempts_non_negative"),
        Index("ix_customers_created_at", "created_at"),
    )

    @property
    def is_seller(self) -> bool:
        return bool(
            self.seller_profile is not None
            and self.seller_profile.application_status == SellerApplicationStatus.APPROVED
        )

    @property
    def seller_status(self) -> Optional[SellerApplicationStatus]:
        if self.seller_profile is None:
            return None
        return self.seller_profile.application_status

    @property
    def seller_store_slug(self) -> Optional[str]:
        if self.seller_profile is None:
            return None
        return self.seller_profile.store_slug

    def __repr__(self) -> str:
        return f"<Customer {self.id}>"


# Prevent duplicate customer accounts regardless of email letter case.
Index("uq_customers_email_lower", func.lower(Customer.email), unique=True)


class CustomerActivity(Base):
    __tablename__ = "customer_activities"

    id: Mapped[uuid.UUID] = uuid_pk()
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    activity_type: Mapped[ActivityType] = mapped_column(enum_col(ActivityType, "activity_type"), nullable=False)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    details: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = created_at_col()

    customer: Mapped[Customer] = relationship(back_populates="activities")
    product: Mapped[Optional["Product"]] = relationship()
    category: Mapped[Optional["Category"]] = relationship()

    __table_args__ = (
        Index("ix_customer_activities_customer_created", "customer_id", "created_at"),
        Index("ix_customer_activities_type", "activity_type"),
    )


class LoginHistory(Base):
    __tablename__ = "login_history"

    id: Mapped[uuid.UUID] = uuid_pk()
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    logout_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # Personal data: collect only where lawful, subject to a retention policy.
    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    browser_info: Mapped[Optional[str]] = mapped_column(String(255))
    device_info: Mapped[Optional[str]] = mapped_column(String(255))
    login_status: Mapped[LoginStatus] = mapped_column(enum_col(LoginStatus, "login_status"), nullable=False)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)

    customer: Mapped[Customer] = relationship(back_populates="login_history")

    __table_args__ = (
        Index("ix_login_history_customer_login", "customer_id", "login_at"),
        CheckConstraint("logout_at IS NULL OR logout_at >= login_at", name="logout_after_login"),
    )
