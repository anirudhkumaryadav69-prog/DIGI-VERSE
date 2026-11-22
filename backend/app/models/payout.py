import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin, created_at_col, updated_at_col, uuid_pk


class PayoutConfiguration(TimestampMixin, Base):
    __tablename__ = "payout_configurations"

    id: Mapped[uuid.UUID] = uuid_pk()
    singleton_key: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, default="default")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    minimum_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    maximum_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    live_execution_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    mock_execution_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    updated_by_admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("admins.id", ondelete="SET NULL")
    )

    __table_args__ = (
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="payout_config_currency_iso4217"),
        CheckConstraint("minimum_amount > 0", name="payout_config_minimum_positive"),
        CheckConstraint("maximum_amount >= minimum_amount", name="payout_config_maximum_valid"),
        CheckConstraint("live_execution_enabled = false", name="payout_config_live_disabled"),
    )


class SellerPayoutAccount(TimestampMixin, Base):
    __tablename__ = "seller_payout_accounts"

    id: Mapped[uuid.UUID] = uuid_pk()
    seller_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seller_profiles.id", ondelete="CASCADE"), nullable=False
    )
    account_type: Mapped[str] = mapped_column(String(16), nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    bank_name: Mapped[Optional[str]] = mapped_column(String(150))
    masked_identifier: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_account_reference: Mapped[Optional[str]] = mapped_column(String(255))
    verification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'unverified'")
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    verified_by_admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("admins.id", ondelete="SET NULL")
    )
    verification_reason: Mapped[Optional[str]] = mapped_column(Text)
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("account_type IN ('bank', 'upi')", name="payout_account_type_valid"),
        CheckConstraint(
            "verification_status IN ('unverified', 'pending', 'verified', 'rejected')",
            name="payout_account_verification_valid",
        ),
        Index("ix_payout_accounts_seller_active", "seller_id", "is_active"),
        Index("ix_payout_accounts_seller_default", "seller_id", "is_default"),
        Index(
            "uq_payout_accounts_one_default",
            "seller_id",
            unique=True,
            postgresql_where=text("is_default AND is_active"),
        ),
    )


class PayoutAccountVerificationHistory(Base):
    __tablename__ = "payout_account_verification_history"

    id: Mapped[uuid.UUID] = uuid_pk()
    payout_account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seller_payout_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seller_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    previous_status: Mapped[str] = mapped_column(String(20), nullable=False)
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
    administrator_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("admins.id", ondelete="RESTRICT"), nullable=False
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)
    administrative_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        CheckConstraint(
            "previous_status IN ('unverified', 'pending', 'verified', 'rejected')",
            name="payout_verification_previous_status_valid",
        ),
        CheckConstraint(
            "new_status IN ('pending', 'verified', 'rejected')",
            name="payout_verification_new_status_valid",
        ),
        CheckConstraint(
            "(new_status = 'rejected' AND rejection_reason IS NOT NULL "
            "AND BTRIM(rejection_reason) <> '') OR new_status <> 'rejected'",
            name="payout_verification_rejection_reason_required",
        ),
        Index("ix_payout_verification_account_created", "payout_account_id", "created_at"),
        Index("ix_payout_verification_seller_created", "seller_id", "created_at"),
        Index("ix_payout_verification_admin_created", "administrator_id", "created_at"),
    )


class PayoutReconciliationHistory(Base):
    __tablename__ = "payout_reconciliation_history"

    id: Mapped[uuid.UUID] = uuid_pk()
    payout_request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("payout_requests.id", ondelete="RESTRICT"), nullable=False
    )
    execution_attempt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("payout_execution_attempts.id", ondelete="RESTRICT")
    )
    settlement_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("financial_transactions.id", ondelete="RESTRICT")
    )
    previous_classification: Mapped[str] = mapped_column(String(32), nullable=False)
    new_classification: Mapped[str] = mapped_column(String(32), nullable=False)
    resolution_action: Mapped[str] = mapped_column(String(32), nullable=False)
    resolution_reason: Mapped[str] = mapped_column(Text, nullable=False)
    administrator_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("admins.id", ondelete="RESTRICT"), nullable=False
    )
    evidence_reference: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        CheckConstraint(
            "resolution_action IN ('investigate', 'confirm_evidence', 'keep_pending', 'mark_resolved')",
            name="payout_reconciliation_resolution_action_valid",
        ),
        CheckConstraint("BTRIM(resolution_reason) <> ''", name="payout_reconciliation_reason_required"),
        Index("ix_payout_reconciliation_request_created", "payout_request_id", "created_at"),
        Index("ix_payout_reconciliation_admin_created", "administrator_id", "created_at"),
        Index("ix_payout_reconciliation_classification", "new_classification"),
    )


class PayoutRequest(TimestampMixin, Base):
    __tablename__ = "payout_requests"

    id: Mapped[uuid.UUID] = uuid_pk()
    seller_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seller_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    payout_account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seller_payout_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'requested'"))
    reservation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'reserved'")
    )
    account_type_snapshot: Mapped[str] = mapped_column(String(16), nullable=False)
    destination_masked_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_account_reference_snapshot: Mapped[Optional[str]] = mapped_column(String(255))
    available_balance_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_by_admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("admins.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    approved_by_admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("admins.id", ondelete="SET NULL")
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    processing_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reconciliation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'not_required'")
    )
    reconciled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reconciled_by_admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("admins.id", ondelete="SET NULL")
    )
    snapshot_metadata: Mapped[dict] = mapped_column("snapshot_metadata", JSONB, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint("amount > 0", name="payout_request_amount_positive"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="payout_request_currency_iso4217"),
        CheckConstraint("available_balance_snapshot >= 0", name="payout_request_available_snapshot_non_negative"),
        CheckConstraint(
            "status IN ('requested', 'under_review', 'approved', 'processing', 'completed', "
            "'rejected', 'failed', 'cancelled', 'uncertain')",
            name="payout_request_status_valid",
        ),
        CheckConstraint(
            "reservation_status IN ('reserved', 'released', 'deducted', 'retained')",
            name="payout_reservation_status_valid",
        ),
        CheckConstraint(
            "account_type_snapshot IN ('bank', 'upi')",
            name="payout_request_account_type_valid",
        ),
        CheckConstraint(
            "reconciliation_status IN ('not_required', 'required', 'reconciled', 'failed')",
            name="payout_reconciliation_status_valid",
        ),
        Index("ix_payout_requests_seller_status", "seller_id", "status"),
        Index("ix_payout_requests_seller_created", "seller_id", "created_at"),
        Index("ix_payout_requests_status_created", "status", "created_at"),
    )


class PayoutExecutionAttempt(TimestampMixin, Base):
    __tablename__ = "payout_execution_attempts"

    id: Mapped[uuid.UUID] = uuid_pk()
    payout_request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("payout_requests.id", ondelete="RESTRICT"), nullable=False
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    provider_name: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_reference: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    uncertain: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    sanitized_error: Mapped[Optional[str]] = mapped_column(String(500))
    started_at: Mapped[datetime] = created_at_col()
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    executed_by_admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("admins.id", ondelete="SET NULL")
    )
    simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (
        CheckConstraint("attempt_no >= 1", name="payout_attempt_number_positive"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'uncertain')",
            name="payout_attempt_status_valid",
        ),
        CheckConstraint(
            "outcome IN ('success', 'failed', 'uncertain')",
            name="payout_attempt_outcome_valid",
        ),
        Index(
            "uq_payout_attempt_request_no",
            "payout_request_id",
            "attempt_no",
            unique=True,
        ),
        Index(
            "uq_payout_attempt_provider_reference",
            "provider_reference",
            unique=True,
            postgresql_where=text("provider_reference IS NOT NULL"),
        ),
        Index("ix_payout_attempt_request_status", "payout_request_id", "status"),
    )
