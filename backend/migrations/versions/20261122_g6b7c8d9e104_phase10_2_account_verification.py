"""phase10_2_account_verification

Revision ID: g6b7c8d9e104
Revises: f5a6b7c8d903
Create Date: 2026-11-22 12:55:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g6b7c8d9e104"
down_revision: Union[str, None] = "f5a6b7c8d903"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payout_account_verification_history",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("payout_account_id", sa.Uuid(), nullable=False),
        sa.Column("seller_id", sa.Uuid(), nullable=False),
        sa.Column("previous_status", sa.String(length=20), nullable=False),
        sa.Column("new_status", sa.String(length=20), nullable=False),
        sa.Column("administrator_id", sa.Uuid(), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("administrative_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["payout_account_id"],
            ["seller_payout_accounts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["seller_id"], ["seller_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["administrator_id"], ["admins.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "previous_status IN ('unverified', 'pending', 'verified', 'rejected')",
            name="payout_verification_previous_status_valid",
        ),
        sa.CheckConstraint(
            "new_status IN ('pending', 'verified', 'rejected')",
            name="payout_verification_new_status_valid",
        ),
        sa.CheckConstraint(
            "(new_status = 'rejected' AND rejection_reason IS NOT NULL "
            "AND BTRIM(rejection_reason) <> '') OR new_status <> 'rejected'",
            name="payout_verification_rejection_reason_required",
        ),
    )
    op.create_index(
        "ix_payout_verification_account_created",
        "payout_account_verification_history",
        ["payout_account_id", "created_at"],
    )
    op.create_index(
        "ix_payout_verification_seller_created",
        "payout_account_verification_history",
        ["seller_id", "created_at"],
    )
    op.create_index(
        "ix_payout_verification_admin_created",
        "payout_account_verification_history",
        ["administrator_id", "created_at"],
    )

    op.execute(
        """
        UPDATE seller_payout_accounts
        SET verification_status = 'pending'
        WHERE verification_status = 'unverified'
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_payout_verification_history_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'payout account verification history is append-only';
        END;
        $$;
        CREATE TRIGGER payout_verification_history_append_only
        BEFORE UPDATE OR DELETE ON payout_account_verification_history
        FOR EACH ROW EXECUTE FUNCTION prevent_payout_verification_history_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS payout_verification_history_append_only "
        "ON payout_account_verification_history"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_payout_verification_history_mutation()")
    op.drop_index("ix_payout_verification_admin_created", table_name="payout_account_verification_history")
    op.drop_index("ix_payout_verification_seller_created", table_name="payout_account_verification_history")
    op.drop_index("ix_payout_verification_account_created", table_name="payout_account_verification_history")
    op.drop_table("payout_account_verification_history")
