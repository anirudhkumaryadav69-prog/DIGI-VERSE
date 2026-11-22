"""phase10_financial_foundation

Revision ID: d2e3f4a5b601
Revises: c9d0e1f2a345
Create Date: 2026-11-22 11:15:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2e3f4a5b601"
down_revision: Union[str, None] = "c9d0e1f2a345"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Immutable commission snapshots on the existing order-item purchase-time data.
    op.add_column("order_items", sa.Column("commission_rate_snapshot", sa.Numeric(9, 6), nullable=True))
    op.add_column("order_items", sa.Column("commission_amount_snapshot", sa.Numeric(12, 2), nullable=True))
    op.add_column("order_items", sa.Column("gross_amount_snapshot", sa.Numeric(12, 2), nullable=True))
    op.add_column("order_items", sa.Column("net_amount_snapshot", sa.Numeric(12, 2), nullable=True))
    op.add_column("order_items", sa.Column("commission_currency_snapshot", sa.String(length=3), nullable=True))
    op.add_column("order_items", sa.Column("commission_source_snapshot", sa.String(length=32), nullable=True))
    op.add_column("order_items", sa.Column("commission_snapshotted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "commission_snapshot_values_valid",
        "order_items",
        "(commission_rate_snapshot IS NULL AND commission_amount_snapshot IS NULL "
        "AND gross_amount_snapshot IS NULL AND net_amount_snapshot IS NULL "
        "AND commission_currency_snapshot IS NULL AND commission_source_snapshot IS NULL "
        "AND commission_snapshotted_at IS NULL) "
        "OR (commission_rate_snapshot >= 0 AND commission_amount_snapshot >= 0 "
        "AND gross_amount_snapshot >= 0 AND net_amount_snapshot >= 0 "
        "AND commission_currency_snapshot ~ '^[A-Z]{3}$' "
        "AND commission_source_snapshot IN ('global_default', 'seller_override', 'platform_owned') "
        "AND commission_snapshotted_at IS NOT NULL)",
    )

    op.create_table(
        "commission_configurations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("singleton_key", sa.String(length=32), nullable=False),
        sa.Column("default_rate", sa.Numeric(9, 6), nullable=False),
        sa.Column("maximum_rate", sa.Numeric(9, 6), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("precision_minor_units", sa.Integer(), server_default=sa.text("2"), nullable=False),
        sa.Column("updated_by_admin_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_admin_id"], ["admins.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("singleton_key"),
        sa.CheckConstraint("default_rate >= 0", name="commission_default_non_negative"),
        sa.CheckConstraint("maximum_rate >= 0", name="commission_maximum_non_negative"),
        sa.CheckConstraint("default_rate <= maximum_rate", name="commission_default_within_maximum"),
        sa.CheckConstraint("precision_minor_units BETWEEN 0 AND 6", name="commission_precision_range"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="commission_currency_iso4217"),
    )
    op.execute(
        "INSERT INTO commission_configurations "
        "(singleton_key, default_rate, maximum_rate, currency, precision_minor_units) "
        "VALUES ('default', 0, 100, 'INR', 2)"
    )

    op.create_table(
        "seller_commission_overrides",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("seller_id", sa.Uuid(), nullable=False),
        sa.Column("rate", sa.Numeric(9, 6), nullable=False),
        sa.Column("updated_by_admin_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["seller_id"], ["seller_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_admin_id"], ["admins.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seller_id"),
        sa.CheckConstraint("rate >= 0", name="seller_commission_non_negative"),
    )
    op.create_check_constraint(
        "seller_override_currency_independent",
        "seller_commission_overrides",
        "rate <= 100",
    )

    op.create_table(
        "commission_history",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("change_type", sa.String(length=32), nullable=False),
        sa.Column("seller_id", sa.Uuid(), nullable=True),
        sa.Column("old_rate", sa.Numeric(9, 6), nullable=True),
        sa.Column("new_rate", sa.Numeric(9, 6), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changed_by_admin_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["seller_id"], ["seller_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["changed_by_admin_id"], ["admins.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "change_type IN ('global_update', 'seller_override_set', 'seller_override_removed')",
            name="commission_history_change_type",
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="commission_history_currency_iso4217"),
    )
    op.create_index("ix_commission_history_seller_created", "commission_history", ["seller_id", "created_at"])
    op.create_index("ix_commission_history_created_at", "commission_history", ["created_at"])

    op.create_table(
        "refund_records",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("refund_id", sa.String(length=100), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("gateway_event_id", sa.String(length=120), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refund_id"),
        sa.UniqueConstraint("gateway_event_id"),
        sa.CheckConstraint("amount > 0", name="refund_amount_positive"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="refund_currency_iso4217"),
        sa.CheckConstraint("status IN ('pending', 'processed', 'failed')", name="refund_status_valid"),
    )
    op.create_index("ix_refunds_payment_status", "refund_records", ["payment_id", "status"])

    op.create_table(
        "financial_transactions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("transaction_type", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'posted'"), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("debit_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("credit_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("order_item_id", sa.Uuid(), nullable=True),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("refund_record_id", sa.Uuid(), nullable=True),
        sa.Column("seller_id", sa.Uuid(), nullable=True),
        sa.Column("provider_transaction_id", sa.String(length=100), nullable=True),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["refund_record_id"], ["refund_records.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["seller_id"], ["seller_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.CheckConstraint("status IN ('posted', 'reversed')", name="financial_transaction_status_valid"),
        sa.CheckConstraint("debit_total >= 0", name="financial_debit_total_non_negative"),
        sa.CheckConstraint("credit_total >= 0", name="financial_credit_total_non_negative"),
        sa.CheckConstraint("debit_total = credit_total", name="financial_transaction_balanced"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="financial_transaction_currency_iso4217"),
        sa.CheckConstraint(
            "transaction_type IN ('payment_capture', 'refund_reversal', 'payment_reversal', 'financial_correction')",
            name="financial_transaction_type_valid",
        ),
    )
    op.create_index("ix_financial_transactions_order_posted", "financial_transactions", ["order_id", "posted_at"])
    op.create_index("ix_financial_transactions_seller_posted", "financial_transactions", ["seller_id", "posted_at"])
    op.create_index("ix_financial_transactions_payment", "financial_transactions", ["payment_id"])
    op.create_index("ix_financial_transactions_refund", "financial_transactions", ["refund_record_id"])

    op.create_table(
        "financial_ledger_entries",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("entry_type", sa.String(length=48), nullable=False),
        sa.Column("account_code", sa.String(length=64), nullable=False),
        sa.Column("direction", sa.String(length=6), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("order_item_id", sa.Uuid(), nullable=True),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("refund_record_id", sa.Uuid(), nullable=True),
        sa.Column("seller_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["financial_transactions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["refund_record_id"], ["refund_records.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["seller_id"], ["seller_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.CheckConstraint("direction IN ('debit', 'credit')", name="ledger_direction_valid"),
        sa.CheckConstraint("amount > 0", name="ledger_amount_positive"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ledger_currency_iso4217"),
        sa.CheckConstraint(
            "entry_type IN ('customer_payment_allocation', 'seller_gross_earnings', "
            "'seller_net_earnings', 'platform_commission_earnings', 'platform_product_revenue', "
            "'refund_adjustment', 'commission_reversal', 'payment_reversal', "
            "'financial_correction', 'payout')",
            name="ledger_entry_type_valid",
        ),
    )
    op.create_index("ix_ledger_transaction", "financial_ledger_entries", ["transaction_id"])
    op.create_index("ix_ledger_order_posted", "financial_ledger_entries", ["order_id", "posted_at"])
    op.create_index("ix_ledger_seller_posted", "financial_ledger_entries", ["seller_id", "posted_at"])
    op.create_index("ix_ledger_payment", "financial_ledger_entries", ["payment_id"])
    op.create_index("ix_ledger_refund", "financial_ledger_entries", ["refund_record_id"])
    op.create_index("ix_ledger_entry_type_posted", "financial_ledger_entries", ["entry_type", "posted_at"])

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_immutable_financial_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'posted financial records are immutable';
        END;
        $$;
        CREATE TRIGGER financial_transactions_immutable
        BEFORE UPDATE OR DELETE ON financial_transactions
        FOR EACH ROW EXECUTE FUNCTION prevent_immutable_financial_mutation();
        CREATE TRIGGER financial_ledger_entries_immutable
        BEFORE UPDATE OR DELETE ON financial_ledger_entries
        FOR EACH ROW EXECUTE FUNCTION prevent_immutable_financial_mutation();
        CREATE TRIGGER commission_history_immutable
        BEFORE UPDATE OR DELETE ON commission_history
        FOR EACH ROW EXECUTE FUNCTION prevent_immutable_financial_mutation();
        """
    )
    # Historical order items receive immutable zero-rate snapshots. New items are snapshotted
    # at checkout; this only establishes a safe historical record for pre-Phase-10 orders.
    op.execute(
        """
        UPDATE order_items
        SET commission_rate_snapshot = 0,
            commission_amount_snapshot = 0,
            gross_amount_snapshot = ROUND(purchase_price * quantity, 2),
            net_amount_snapshot = ROUND(purchase_price * quantity, 2),
            commission_currency_snapshot = 'INR',
            commission_source_snapshot = 'global_default',
            commission_snapshotted_at = COALESCE(
                (SELECT created_at FROM orders WHERE orders.id = order_items.order_id),
                now()
            )
        WHERE commission_rate_snapshot IS NULL
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_commission_snapshot_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (
                OLD.commission_rate_snapshot IS NULL
                AND OLD.commission_amount_snapshot IS NULL
                AND OLD.gross_amount_snapshot IS NULL
                AND OLD.net_amount_snapshot IS NULL
                AND OLD.commission_currency_snapshot IS NULL
                AND OLD.commission_source_snapshot IS NULL
                AND OLD.commission_snapshotted_at IS NULL
            ) THEN
                RETURN NEW;
            END IF;
            IF (
                NEW.commission_rate_snapshot IS DISTINCT FROM OLD.commission_rate_snapshot
                OR NEW.commission_amount_snapshot IS DISTINCT FROM OLD.commission_amount_snapshot
                OR NEW.gross_amount_snapshot IS DISTINCT FROM OLD.gross_amount_snapshot
                OR NEW.net_amount_snapshot IS DISTINCT FROM OLD.net_amount_snapshot
                OR NEW.commission_currency_snapshot IS DISTINCT FROM OLD.commission_currency_snapshot
                OR NEW.commission_source_snapshot IS DISTINCT FROM OLD.commission_source_snapshot
                OR NEW.commission_snapshotted_at IS DISTINCT FROM OLD.commission_snapshotted_at
            ) THEN
                RAISE EXCEPTION 'commission snapshots are immutable';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER order_items_commission_snapshot_immutable
        BEFORE UPDATE ON order_items
        FOR EACH ROW EXECUTE FUNCTION prevent_commission_snapshot_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS order_items_commission_snapshot_immutable ON order_items")
    op.execute("DROP FUNCTION IF EXISTS prevent_commission_snapshot_mutation()")
    op.execute("DROP TRIGGER IF EXISTS financial_transactions_immutable ON financial_transactions")
    op.execute("DROP TRIGGER IF EXISTS financial_ledger_entries_immutable ON financial_ledger_entries")
    op.execute("DROP TRIGGER IF EXISTS commission_history_immutable ON commission_history")
    op.execute("DROP FUNCTION IF EXISTS prevent_immutable_financial_mutation()")

    op.drop_index("ix_ledger_entry_type_posted", table_name="financial_ledger_entries")
    op.drop_index("ix_ledger_refund", table_name="financial_ledger_entries")
    op.drop_index("ix_ledger_payment", table_name="financial_ledger_entries")
    op.drop_index("ix_ledger_seller_posted", table_name="financial_ledger_entries")
    op.drop_index("ix_ledger_order_posted", table_name="financial_ledger_entries")
    op.drop_index("ix_ledger_transaction", table_name="financial_ledger_entries")
    op.drop_table("financial_ledger_entries")

    op.drop_index("ix_financial_transactions_refund", table_name="financial_transactions")
    op.drop_index("ix_financial_transactions_payment", table_name="financial_transactions")
    op.drop_index("ix_financial_transactions_seller_posted", table_name="financial_transactions")
    op.drop_index("ix_financial_transactions_order_posted", table_name="financial_transactions")
    op.drop_table("financial_transactions")

    op.drop_index("ix_refunds_payment_status", table_name="refund_records")
    op.drop_table("refund_records")

    op.drop_index("ix_commission_history_created_at", table_name="commission_history")
    op.drop_index("ix_commission_history_seller_created", table_name="commission_history")
    op.drop_table("commission_history")
    op.drop_table("seller_commission_overrides")
    op.drop_table("commission_configurations")

    op.drop_constraint("commission_snapshot_values_valid", "order_items", type_="check")
    op.drop_column("order_items", "commission_snapshotted_at")
    op.drop_column("order_items", "commission_source_snapshot")
    op.drop_column("order_items", "commission_currency_snapshot")
    op.drop_column("order_items", "net_amount_snapshot")
    op.drop_column("order_items", "gross_amount_snapshot")
    op.drop_column("order_items", "commission_amount_snapshot")
    op.drop_column("order_items", "commission_rate_snapshot")
