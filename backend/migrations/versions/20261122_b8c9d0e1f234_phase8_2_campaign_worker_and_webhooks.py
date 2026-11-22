"""phase8_2_campaign_worker_and_webhooks

Revision ID: b8c9d0e1f234
Revises: f4b9c2d8a102
Create Date: 2026-11-22 09:30:00.000000+00:00

"""
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f234"
down_revision: Union[str, None] = "f4b9c2d8a102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_enum_check_constraints(table_name: str, column_name: str) -> None:
    if table_name not in {"email_campaigns", "whatsapp_campaigns", "campaign_recipients"}:
        raise ValueError(f"Unexpected table: {table_name}")
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT c.conname
              FROM pg_constraint c
              JOIN pg_class t ON c.conrelid = t.oid
              JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
             WHERE t.relname = :table_name
               AND c.contype = 'c'
               AND a.attname = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).scalars().all()
    for conname in rows:
        if not re.fullmatch(r"[A-Za-z0-9_]+", conname):
            raise ValueError(f"Unsafe constraint identifier: {conname}")
        bind.execute(sa.text(f'ALTER TABLE "{table_name}" DROP CONSTRAINT IF EXISTS "{conname}"'))


def upgrade() -> None:
    # 1. Extend email_campaigns and whatsapp_campaigns for persistent scheduling & locking
    for tbl in ("email_campaigns", "whatsapp_campaigns"):
        op.add_column(tbl, sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True))
        op.add_column(tbl, sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(tbl, sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(tbl, sa.Column("locked_by", sa.String(length=120), nullable=True))
        op.add_column(tbl, sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(tbl, sa.Column("last_error", sa.Text(), nullable=True))

    _drop_enum_check_constraints("email_campaigns", "status")
    op.create_check_constraint(
        "email_campaign_status",
        "email_campaigns",
        "status IN ('draft', 'scheduled', 'queued', 'sending', 'processing', 'completed', 'partially_completed', 'cancelled', 'failed')",
    )
    _drop_enum_check_constraints("whatsapp_campaigns", "status")
    op.create_check_constraint(
        "whatsapp_campaign_status",
        "whatsapp_campaigns",
        "status IN ('draft', 'scheduled', 'queued', 'sending', 'processing', 'completed', 'partially_completed', 'cancelled', 'failed')",
    )

    op.create_index(
        "ix_email_campaigns_status_scheduled",
        "email_campaigns",
        ["status", "scheduled_for"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_campaigns_status_scheduled",
        "whatsapp_campaigns",
        ["status", "scheduled_for"],
        unique=False,
    )

    # 2. Extend campaign_recipients for durable job queues, retry backoff, locking, & telemetry
    op.add_column("campaign_recipients", sa.Column("idempotency_key", sa.String(length=120), nullable=True))
    op.add_column(
        "campaign_recipients",
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "campaign_recipients",
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("5"), nullable=False),
    )
    op.add_column("campaign_recipients", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("campaign_recipients", sa.Column("locked_by", sa.String(length=120), nullable=True))
    op.add_column("campaign_recipients", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("campaign_recipients", sa.Column("error_code", sa.String(length=80), nullable=True))
    op.add_column("campaign_recipients", sa.Column("is_retryable_error", sa.Boolean(), nullable=True))
    op.add_column(
        "campaign_recipients",
        sa.Column("provider_response_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("campaign_recipients", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("campaign_recipients", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("campaign_recipients", sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("campaign_recipients", sa.Column("bounced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("campaign_recipients", sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "campaign_recipients",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    _drop_enum_check_constraints("campaign_recipients", "delivery_status")
    op.create_check_constraint(
        "delivery_status",
        "campaign_recipients",
        "delivery_status IN ('queued', 'processing', 'retrying', 'accepted', 'sent', 'delivered', 'read', 'bounced', 'failed', 'suppressed', 'skipped', 'unresolved')",
    )
    op.create_check_constraint(
        "attempt_count_non_negative",
        "campaign_recipients",
        "attempt_count >= 0",
    )
    op.create_check_constraint(
        "max_attempts_positive",
        "campaign_recipients",
        "max_attempts >= 1",
    )
    op.create_unique_constraint(
        op.f("uq_campaign_recipients_idempotency_key"),
        "campaign_recipients",
        ["idempotency_key"],
    )
    op.create_index(
        "ix_campaign_recipients_worker_poll",
        "campaign_recipients",
        ["delivery_status", "next_retry_at", "locked_at"],
        unique=False,
    )

    # 3. Persistent marketing webhook event idempotency ledger
    op.create_table(
        "marketing_webhook_events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=180), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("provider_message_id", sa.String(length=150), nullable=True),
        sa.Column("campaign_recipient_id", sa.Uuid(), nullable=True),
        sa.Column(
            "processing_status",
            sa.String(length=40),
            server_default=sa.text("'processed'"),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_recipient_id"],
            ["campaign_recipients.id"],
            name=op.f("fk_marketing_webhook_events_campaign_recipient_id_campaign_recipients"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_marketing_webhook_events")),
        sa.UniqueConstraint("provider", "event_id", name="uq_marketing_webhook_provider_event_id"),
    )
    op.create_index(
        op.f("ix_marketing_webhook_events_provider_message_id"),
        "marketing_webhook_events",
        ["provider_message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_marketing_webhook_events_campaign_recipient_id"),
        "marketing_webhook_events",
        ["campaign_recipient_id"],
        unique=False,
    )
    op.create_index(
        "ix_marketing_webhook_events_received",
        "marketing_webhook_events",
        ["received_at"],
        unique=False,
    )

    # 4. Worker heartbeats table for liveness monitoring & recovery visibility
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(length=120), nullable=False),
        sa.Column("hostname", sa.String(length=150), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'running'"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_jobs_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("worker_id", name=op.f("pk_worker_heartbeats")),
    )


def downgrade() -> None:
    op.drop_table("worker_heartbeats")

    op.drop_index("ix_marketing_webhook_events_received", table_name="marketing_webhook_events")
    op.drop_index(op.f("ix_marketing_webhook_events_campaign_recipient_id"), table_name="marketing_webhook_events")
    op.drop_index(op.f("ix_marketing_webhook_events_provider_message_id"), table_name="marketing_webhook_events")
    op.drop_table("marketing_webhook_events")

    op.drop_index("ix_campaign_recipients_worker_poll", table_name="campaign_recipients")
    op.drop_constraint(op.f("uq_campaign_recipients_idempotency_key"), "campaign_recipients", type_="unique")
    op.drop_constraint(op.f("ck_campaign_recipients_max_attempts_positive"), "campaign_recipients", type_="check")
    op.drop_constraint(op.f("ck_campaign_recipients_attempt_count_non_negative"), "campaign_recipients", type_="check")
    _drop_enum_check_constraints("campaign_recipients", "delivery_status")
    op.execute(
        """
        UPDATE campaign_recipients
           SET delivery_status = CASE
               WHEN delivery_status IN ('processing', 'retrying') THEN 'queued'
               WHEN delivery_status = 'accepted' THEN 'sent'
               WHEN delivery_status IN ('bounced', 'suppressed', 'unresolved') THEN 'failed'
               ELSE delivery_status
           END
        """
    )
    op.create_check_constraint(
        "delivery_status",
        "campaign_recipients",
        "delivery_status IN ('queued', 'sent', 'delivered', 'read', 'failed', 'skipped')",
    )

    for col in (
        "updated_at",
        "failed_at",
        "bounced_at",
        "read_at",
        "delivered_at",
        "accepted_at",
        "provider_response_metadata",
        "is_retryable_error",
        "error_code",
        "locked_at",
        "locked_by",
        "next_retry_at",
        "max_attempts",
        "attempt_count",
        "idempotency_key",
    ):
        op.drop_column("campaign_recipients", col)

    op.drop_index("ix_whatsapp_campaigns_status_scheduled", table_name="whatsapp_campaigns")
    op.drop_index("ix_email_campaigns_status_scheduled", table_name="email_campaigns")

    for tbl, cname, enums in (
        ("whatsapp_campaigns", "whatsapp_campaign_status", "('draft', 'scheduled', 'sending', 'completed', 'cancelled', 'failed')"),
        ("email_campaigns", "email_campaign_status", "('draft', 'scheduled', 'sending', 'completed', 'cancelled', 'failed')"),
    ):
        _drop_enum_check_constraints(tbl, "status")
        op.execute(
            f"""
            UPDATE {tbl}
               SET status = CASE
                   WHEN status IN ('queued', 'processing') THEN 'sending'
                   WHEN status = 'partially_completed' THEN 'completed'
                   ELSE status
               END
            """
        )
        op.create_check_constraint(cname, tbl, f"status IN {enums}")
        for col in ("last_error", "locked_at", "locked_by", "started_at", "queued_at", "scheduled_for"):
            op.drop_column(tbl, col)
