"""Authentication & session persistence models:
- AuthSession: server-side refresh-token families, rotation, and reuse detection for Customers & Admins.
- PhoneOTPChallenge: hashed, single-use, attempt-limited OTP challenges for phone verification & updates.
- PasswordResetToken: hashed, single-use password reset tokens with expiry.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AuthSubjectType, OTPPurpose
from app.models.mixins import created_at_col, enum_col, uuid_pk

if TYPE_CHECKING:
    from app.models.admin import Admin
    from app.models.customer import Customer


class AuthSession(Base):
    """Server-side refresh-token session supporting rotation, reuse detection, and instant revocation."""

    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    subject_type: Mapped[AuthSubjectType] = mapped_column(
        enum_col(AuthSubjectType, "auth_subject_type"), nullable=False
    )
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("admins.id", ondelete="CASCADE"), index=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, default=uuid.uuid4, index=True)
    # SHA-256 hash of the active refresh token; raw refresh tokens are never stored.
    refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    # SHA-256 hash of the immediately preceding refresh token in this rotation chain (for reuse detection).
    previous_token_hash: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64))
    user_agent: Mapped[Optional[str]] = mapped_column(String(512))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = created_at_col()
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    customer: Mapped[Optional["Customer"]] = relationship(back_populates="sessions")
    admin: Mapped[Optional["Admin"]] = relationship(back_populates="sessions")

    __table_args__ = (
        CheckConstraint(
            "(subject_type = 'customer' AND customer_id IS NOT NULL AND admin_id IS NULL) OR "
            "(subject_type = 'admin' AND admin_id IS NOT NULL AND customer_id IS NULL)",
            name="subject_matches_owner_fk",
        ),
        Index("ix_auth_sessions_active_expires", "revoked_at", "expires_at"),
    )


class PhoneOTPChallenge(Base):
    """Cryptographically hashed OTP challenge with 5-minute expiry, attempt limits, and single-use guard."""

    __tablename__ = "phone_otp_challenges"

    id: Mapped[uuid.UUID] = uuid_pk()
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    purpose: Mapped[OTPPurpose] = mapped_column(enum_col(OTPPurpose, "otp_purpose"), nullable=False)
    # HMAC-SHA256 hash of the OTP code; plaintext OTPs are never stored.
    otp_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()

    customer: Mapped["Customer"] = relationship(back_populates="otp_challenges")

    __table_args__ = (
        CheckConstraint("phone_number ~ '^\\+[1-9][0-9]{7,14}$'", name="phone_e164"),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
        CheckConstraint("max_attempts >= 1", name="max_attempts_positive"),
        Index("ix_phone_otp_challenges_customer_created", "customer_id", "created_at"),
    )


class PasswordResetToken(Base):
    """Hashed, single-use password reset token with expiration."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = uuid_pk()
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SHA-256 hash of the raw URL-safe reset token; plaintext token is never stored.
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    requested_ip: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_at_col()

    customer: Mapped["Customer"] = relationship(back_populates="password_reset_tokens")

    __table_args__ = (
        Index("ix_password_reset_tokens_customer_created", "customer_id", "created_at"),
    )


class RateLimitBucket(Base):
    """Shared PostgreSQL-backed rate-limit counter bucket across multiple backend workers."""

    __tablename__ = "rate_limit_buckets"

    bucket_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("hit_count >= 0", name="hit_count_non_negative"),
        Index("ix_rate_limit_buckets_updated_at", "updated_at"),
    )
