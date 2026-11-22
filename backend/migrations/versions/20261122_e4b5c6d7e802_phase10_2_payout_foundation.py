"""phase10_2_payout_foundation

Revision ID: e4b5c6d7e802
Revises: d2e3f4a5b601
Create Date: 2026-11-22 12:05:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e4b5c6d7e802"
down_revision: Union[str, None] = "d2e3f4a5b601"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payout_configurations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("singleton_key", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("minimum_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("maximum_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("live_execution_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("mock_execution_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("updated_by_admin_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_admin_id"], ["admins.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("singleton_key"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="payout_config_currency_iso4217"),
        sa.CheckConstraint("minimum_amount > 0", name="payout_config_minimum_positive"),
        sa.CheckConstraint("maximum_amount >= minimum_amount", name="payout_config_maximum_valid"),
        sa.CheckConstraint("live_execution_enabled = false", name="payout_config_live_disabled"),
    )
    op.execute(
        """
        INSERT INTO payout_configurations
            (singleton_key, currency, minimum_amount, maximum_amount,
             live_execution_enabled, mock_execution_enabled)
        VALUES ('default', 'INR', 500.00, 100000.00, false, true)
        """
    )

    op.create_table(
        "seller_payout_accounts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("seller_id", sa.Uuid(), nullable=False),
        sa.Column("account_type", sa.String(length=16), nullable=False),
        sa.Column("display_name", sa.String(length=150), nullable=False),
        sa.Column("bank_name", sa.String(length=150), nullable=True),
        sa.Column("masked_identifier", sa.String(length=64), nullable=False),
        sa.Column("provider_account_reference", sa.String(length=255), nullable=True),
        sa.Column("verification_status", sa.String(length=20), server_default=sa.text("'unverified'"), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by_admin_id", sa.Uuid(), nullable=True),
        sa.Column("verification_reason", sa.Text(), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["seller_id"], ["seller_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by_admin_id"], ["admins.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("account_type IN ('bank', 'upi')", name="payout_account_type_valid"),
        sa.CheckConstraint(
            "verification_status IN ('unverified', 'pending', 'verified', 'rejected')",
            name="payout_account_verification_valid",
        ),
    )
    op.create_index("ix_payout_accounts_seller_active", "seller_payout_accounts", ["seller_id", "is_active"])
    op.create_index("ix_payout_accounts_seller_default", "seller_payout_accounts", ["seller_id", "is_default"])
    op.create_index(
        "uq_payout_accounts_one_default",
        "seller_payout_accounts",
        ["seller_id"],
        unique=True,
        postgresql_where=sa.text("is_default AND is_active"),
    )

    op.create_table(
        "payout_requests",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("seller_id", sa.Uuid(), nullable=False),
        sa.Column("payout_account_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'requested'"), nullable=False),
        sa.Column("reservation_status", sa.String(length=20), server_default=sa.text("'reserved'"), nullable=False),
        sa.Column("account_type_snapshot", sa.String(length=16), nullable=False),
        sa.Column("destination_masked_snapshot", sa.String(length=64), nullable=False),
        sa.Column("provider_account_reference_snapshot", sa.String(length=255), nullable=True),
        sa.Column("available_balance_snapshot", sa.Numeric(12, 2), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by_admin_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_admin_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snapshot_metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["seller_id"], ["seller_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payout_account_id"], ["seller_payout_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_admin_id"], ["admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_admin_id"], ["admins.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.CheckConstraint("amount > 0", name="payout_request_amount_positive"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="payout_request_currency_iso4217"),
        sa.CheckConstraint("available_balance_snapshot >= 0", name="payout_request_available_snapshot_non_negative"),
        sa.CheckConstraint(
            "status IN ('requested', 'under_review', 'approved', 'processing', 'completed', "
            "'rejected', 'failed', 'cancelled', 'uncertain')",
            name="payout_request_status_valid",
        ),
        sa.CheckConstraint(
            "reservation_status IN ('reserved', 'released', 'deducted', 'retained')",
            name="payout_reservation_status_valid",
        ),
        sa.CheckConstraint("account_type_snapshot IN ('bank', 'upi')", name="payout_request_account_type_valid"),
    )
    op.create_index("ix_payout_requests_seller_status", "payout_requests", ["seller_id", "status"])
    op.create_index("ix_payout_requests_seller_created", "payout_requests", ["seller_id", "created_at"])
    op.create_index("ix_payout_requests_status_created", "payout_requests", ["status", "created_at"])

    op.create_table(
        "payout_execution_attempts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("payout_request_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("provider_name", sa.String(length=32), nullable=False),
        sa.Column("provider_reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("retryable", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("uncertain", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sanitized_error", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["payout_request_id"], ["payout_requests.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.CheckConstraint("attempt_no >= 1", name="payout_attempt_number_positive"),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'uncertain')",
            name="payout_attempt_status_valid",
        ),
        sa.CheckConstraint("outcome IN ('success', 'failed', 'uncertain')", name="payout_attempt_outcome_valid"),
        sa.UniqueConstraint("payout_request_id", "attempt_no", name="uq_payout_attempt_request_no"),
    )
    op.create_index("ix_payout_attempt_request_status", "payout_execution_attempts", ["payout_request_id", "status"])

    op.drop_constraint("financial_transaction_type_valid", "financial_transactions", type_="check")
    op.create_check_constraint(
        "financial_transaction_type_valid",
        "financial_transactions",
        "transaction_type IN ('payment_capture', 'refund_reversal', 'payment_reversal', "
        "'financial_correction', 'payout_settlement')",
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_payout_snapshot_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (
                NEW.amount IS DISTINCT FROM OLD.amount
                OR NEW.currency IS DISTINCT FROM OLD.currency
                OR NEW.payout_account_id IS DISTINCT FROM OLD.payout_account_id
                OR NEW.account_type_snapshot IS DISTINCT FROM OLD.account_type_snapshot
                OR NEW.destination_masked_snapshot IS DISTINCT FROM OLD.destination_masked_snapshot
                OR NEW.provider_account_reference_snapshot IS DISTINCT FROM OLD.provider_account_reference_snapshot
                OR NEW.available_balance_snapshot IS DISTINCT FROM OLD.available_balance_snapshot
                OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
                OR NEW.seller_id IS DISTINCT FROM OLD.seller_id
            ) THEN
                RAISE EXCEPTION 'payout request immutable financial snapshots cannot be changed';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER payout_request_snapshot_immutable
        BEFORE UPDATE ON payout_requests
        FOR EACH ROW EXECUTE FUNCTION prevent_payout_snapshot_mutation();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_payout_execution_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'payout execution attempts are append-only';
        END;
        $$;
        CREATE TRIGGER payout_execution_attempt_immutable
        BEFORE UPDATE OR DELETE ON payout_execution_attempts
        FOR EACH ROW EXECUTE FUNCTION prevent_payout_execution_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS payout_execution_attempt_immutable ON payout_execution_attempts")
    op.execute("DROP FUNCTION IF EXISTS prevent_payout_execution_mutation()")
    op.execute("DROP TRIGGER IF EXISTS payout_request_snapshot_immutable ON payout_requests")
    op.execute("DROP FUNCTION IF EXISTS prevent_payout_snapshot_mutation()")

    op.drop_constraint("financial_transaction_type_valid", "financial_transactions", type_="check")
    op.create_check_constraint(
        "financial_transaction_type_valid",
        "financial_transactions",
        "transaction_type IN ('payment_capture', 'refund_reversal', 'payment_reversal', 'financial_correction')",
    )

    op.drop_index("ix_payout_attempt_request_status", table_name="payout_execution_attempts")
    op.drop_table("payout_execution_attempts")

    op.drop_index("ix_payout_requests_status_created", table_name="payout_requests")
    op.drop_index("ix_payout_requests_seller_created", table_name="payout_requests")
    op.drop_index("ix_payout_requests_seller_status", table_name="payout_requests")
    op.drop_table("payout_requests")

    op.drop_index("uq_payout_accounts_one_default", table_name="seller_payout_accounts")
    op.drop_index("ix_payout_accounts_seller_default", table_name="seller_payout_accounts")
    op.drop_index("ix_payout_accounts_seller_active", table_name="seller_payout_accounts")
    op.drop_table("seller_payout_accounts")

    op.drop_table("payout_configurations")
