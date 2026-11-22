"""phase10_2_payout_execution

Revision ID: f5a6b7c8d903
Revises: e4b5c6d7e802
Create Date: 2026-11-22 12:35:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f5a6b7c8d903"
down_revision: Union[str, None] = "e4b5c6d7e802"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payout_requests",
        sa.Column("reconciliation_status", sa.String(length=20), server_default=sa.text("'not_required'"), nullable=False),
    )
    op.add_column("payout_requests", sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payout_requests", sa.Column("reconciled_by_admin_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_payout_requests_reconciled_by_admin",
        "payout_requests",
        "admins",
        ["reconciled_by_admin_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "payout_reconciliation_status_valid",
        "payout_requests",
        "reconciliation_status IN ('not_required', 'required', 'reconciled', 'failed')",
    )

    op.add_column(
        "payout_execution_attempts",
        sa.Column("executed_by_admin_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "payout_execution_attempts",
        sa.Column("simulated", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_foreign_key(
        "fk_payout_attempts_executed_by_admin",
        "payout_execution_attempts",
        "admins",
        ["executed_by_admin_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_payout_attempt_provider_reference",
        "payout_execution_attempts",
        ["provider_reference"],
        unique=True,
        postgresql_where=sa.text("provider_reference IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_payout_attempt_provider_reference", table_name="payout_execution_attempts")
    op.drop_constraint(
        "fk_payout_attempts_executed_by_admin",
        "payout_execution_attempts",
        type_="foreignkey",
    )
    op.drop_column("payout_execution_attempts", "simulated")
    op.drop_column("payout_execution_attempts", "executed_by_admin_id")

    op.drop_constraint(
        "payout_reconciliation_status_valid",
        "payout_requests",
        type_="check",
    )
    op.drop_constraint(
        "fk_payout_requests_reconciled_by_admin",
        "payout_requests",
        type_="foreignkey",
    )
    op.drop_column("payout_requests", "reconciled_by_admin_id")
    op.drop_column("payout_requests", "reconciled_at")
    op.drop_column("payout_requests", "reconciliation_status")
