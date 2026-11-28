"""phase10_2_payout_reconciliation

Revision ID: h7c8d9e0f205
Revises: g6b7c8d9e104
Create Date: 2026-11-22 13:20:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h7c8d9e0f205"
down_revision: Union[str, None] = "g6b7c8d9e104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("financial_transaction_type_valid", "financial_transactions", type_="check")
    op.create_check_constraint(
        "financial_transaction_type_valid",
        "financial_transactions",
        "transaction_type IN ('payment_capture', 'refund_reversal', 'payment_reversal', "
        "'financial_correction', 'payout_settlement')",
    )

    op.create_table(
        "payout_reconciliation_history",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("payout_request_id", sa.Uuid(), nullable=False),
        sa.Column("execution_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("settlement_transaction_id", sa.Uuid(), nullable=True),
        sa.Column("previous_classification", sa.String(length=32), nullable=False),
        sa.Column("new_classification", sa.String(length=32), nullable=False),
        sa.Column("resolution_action", sa.String(length=32), nullable=False),
        sa.Column("resolution_reason", sa.Text(), nullable=False),
        sa.Column("administrator_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_reference", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["payout_request_id"], ["payout_requests.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["execution_attempt_id"],
            ["payout_execution_attempts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["settlement_transaction_id"],
            ["financial_transactions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["administrator_id"], ["admins.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "resolution_action IN ('investigate', 'confirm_evidence', 'keep_pending', 'mark_resolved')",
            name="payout_reconciliation_resolution_action_valid",
        ),
        sa.CheckConstraint("BTRIM(resolution_reason) <> ''", name="payout_reconciliation_reason_required"),
    )
    op.create_index(
        "ix_payout_reconciliation_request_created",
        "payout_reconciliation_history",
        ["payout_request_id", "created_at"],
    )
    op.create_index(
        "ix_payout_reconciliation_admin_created",
        "payout_reconciliation_history",
        ["administrator_id", "created_at"],
    )
    op.create_index(
        "ix_payout_reconciliation_classification",
        "payout_reconciliation_history",
        ["new_classification"],
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_payout_reconciliation_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'payout reconciliation history is append-only';
        END;
        $$;
        CREATE TRIGGER payout_reconciliation_history_append_only
        BEFORE UPDATE OR DELETE ON payout_reconciliation_history
        FOR EACH ROW EXECUTE FUNCTION prevent_payout_reconciliation_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS payout_reconciliation_history_append_only "
        "ON payout_reconciliation_history"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_payout_reconciliation_mutation()")
    op.drop_index("ix_payout_reconciliation_classification", table_name="payout_reconciliation_history")
    op.drop_index("ix_payout_reconciliation_admin_created", table_name="payout_reconciliation_history")
    op.drop_index("ix_payout_reconciliation_request_created", table_name="payout_reconciliation_history")
    op.drop_table("payout_reconciliation_history")

    op.drop_constraint("financial_transaction_type_valid", "financial_transactions", type_="check")
    op.create_check_constraint(
        "financial_transaction_type_valid",
        "financial_transactions",
        "transaction_type IN ('payment_capture', 'refund_reversal', 'payment_reversal', "
        "'financial_correction')",
    )
