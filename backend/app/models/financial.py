import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, created_at_col, updated_at_col, uuid_pk


class CommissionConfiguration(TimestampMixin, Base):
    __tablename__ = "commission_configurations"

    id: Mapped[uuid.UUID] = uuid_pk()
    singleton_key: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, default="default")
    default_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    maximum_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    precision_minor_units: Mapped[int] = mapped_column(
        nullable=False, default=2, server_default=text("2")
    )
    updated_by_admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("admins.id", ondelete="SET NULL")
    )

    __table_args__ = (
        CheckConstraint("default_rate >= 0", name="commission_default_non_negative"),
        CheckConstraint("maximum_rate >= 0", name="commission_maximum_non_negative"),
        CheckConstraint("default_rate <= maximum_rate", name="commission_default_within_maximum"),
        CheckConstraint("precision_minor_units BETWEEN 0 AND 6", name="commission_precision_range"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="commission_currency_iso4217"),
    )


class SellerCommissionOverride(TimestampMixin, Base):
    __tablename__ = "seller_commission_overrides"

    id: Mapped[uuid.UUID] = uuid_pk()
    seller_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seller_profiles.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    updated_by_admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("admins.id", ondelete="SET NULL")
    )

    __table_args__ = (
        CheckConstraint("rate >= 0", name="seller_commission_non_negative"),
    )


class CommissionHistory(Base):
    __tablename__ = "commission_history"

    id: Mapped[uuid.UUID] = uuid_pk()
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    seller_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("seller_profiles.id", ondelete="SET NULL")
    )
    old_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    new_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    changed_by_admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("admins.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        CheckConstraint("change_type IN ('global_update', 'seller_override_set', 'seller_override_removed')",
                        name="commission_history_change_type"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="commission_history_currency_iso4217"),
        Index("ix_commission_history_seller_created", "seller_id", "created_at"),
        Index("ix_commission_history_created_at", "created_at"),
    )


class RefundRecord(TimestampMixin, Base):
    __tablename__ = "refund_records"

    id: Mapped[uuid.UUID] = uuid_pk()
    payment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False
    )
    refund_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    gateway_event_id: Mapped[Optional[str]] = mapped_column(String(120), unique=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("amount > 0", name="refund_amount_positive"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="refund_currency_iso4217"),
        CheckConstraint("status IN ('pending', 'processed', 'failed')", name="refund_status_valid"),
        Index("ix_refunds_payment_status", "payment_id", "status"),
    )


class FinancialTransaction(Base):
    __tablename__ = "financial_transactions"

    id: Mapped[uuid.UUID] = uuid_pk()
    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'posted'"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    debit_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    credit_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="RESTRICT")
    )
    order_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("order_items.id", ondelete="RESTRICT")
    )
    payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("payments.id", ondelete="RESTRICT")
    )
    refund_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("refund_records.id", ondelete="RESTRICT")
    )
    seller_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("seller_profiles.id", ondelete="SET NULL")
    )
    provider_transaction_id: Mapped[Optional[str]] = mapped_column(String(100))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    posted_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        CheckConstraint("status IN ('posted', 'reversed')", name="financial_transaction_status_valid"),
        CheckConstraint("debit_total >= 0", name="financial_debit_total_non_negative"),
        CheckConstraint("credit_total >= 0", name="financial_credit_total_non_negative"),
        CheckConstraint("debit_total = credit_total", name="financial_transaction_balanced"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="financial_transaction_currency_iso4217"),
        CheckConstraint(
            "transaction_type IN ('payment_capture', 'refund_reversal', 'payment_reversal', "
            "'financial_correction', 'payout_settlement')",
            name="financial_transaction_type_valid",
        ),
        Index("ix_financial_transactions_order_posted", "order_id", "posted_at"),
        Index("ix_financial_transactions_seller_posted", "seller_id", "posted_at"),
        Index("ix_financial_transactions_payment", "payment_id"),
        Index("ix_financial_transactions_refund", "refund_record_id"),
    )


class FinancialLedgerEntry(Base):
    __tablename__ = "financial_ledger_entries"

    id: Mapped[uuid.UUID] = uuid_pk()
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("financial_transactions.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    entry_type: Mapped[str] = mapped_column(String(48), nullable=False)
    account_code: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(6), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="RESTRICT")
    )
    order_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("order_items.id", ondelete="RESTRICT")
    )
    payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("payments.id", ondelete="RESTRICT")
    )
    refund_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("refund_records.id", ondelete="RESTRICT")
    )
    seller_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("seller_profiles.id", ondelete="SET NULL")
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    posted_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        CheckConstraint("direction IN ('debit', 'credit')", name="ledger_direction_valid"),
        CheckConstraint("amount > 0", name="ledger_amount_positive"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ledger_currency_iso4217"),
        CheckConstraint(
            "entry_type IN ('customer_payment_allocation', 'seller_gross_earnings', "
            "'seller_net_earnings', 'platform_commission_earnings', 'platform_product_revenue', "
            "'refund_adjustment', 'commission_reversal', 'payment_reversal', "
            "'financial_correction', 'payout')",
            name="ledger_entry_type_valid",
        ),
        Index("ix_ledger_transaction", "transaction_id"),
        Index("ix_ledger_order_posted", "order_id", "posted_at"),
        Index("ix_ledger_seller_posted", "seller_id", "posted_at"),
        Index("ix_ledger_payment", "payment_id"),
        Index("ix_ledger_refund", "refund_record_id"),
        Index("ix_ledger_entry_type_posted", "entry_type", "posted_at"),
    )
