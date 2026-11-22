"""add_rate_limit_buckets_and_perf_indexes

Revision ID: e1a7f3c9d201
Revises: bcf03aa639b3
Create Date: 2026-11-22 07:05:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1a7f3c9d201"
down_revision: Union[str, None] = "bcf03aa639b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_buckets",
        sa.Column("bucket_key", sa.String(length=200), nullable=False),
        sa.Column(
            "window_start",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("hit_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("hit_count >= 0", name=op.f("ck_rate_limit_buckets_hit_count_non_negative")),
        sa.PrimaryKeyConstraint("bucket_key", name=op.f("pk_rate_limit_buckets")),
    )
    op.create_index(
        op.f("ix_rate_limit_buckets_updated_at"),
        "rate_limit_buckets",
        ["updated_at"],
        unique=False,
    )

    # Query-pattern aligned indexes verified via EXPLAIN ANALYZE
    op.create_index(
        "ix_products_active_category_created",
        "products",
        ["is_active", "category_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_sales_active_window",
        "sales",
        ["product_id", "starts_at", "expires_at"],
        unique=False,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_orders_payment_status_created",
        "orders",
        ["payment_status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_orders_created_at",
        "orders",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_payments_status",
        "payments",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_download_records_customer_downloaded",
        "download_records",
        ["customer_id", "downloaded_at"],
        unique=False,
    )
    op.create_index(
        "ix_download_records_downloaded_at",
        "download_records",
        ["downloaded_at"],
        unique=False,
    )
    op.create_index(
        "ix_customers_created_at",
        "customers",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_customers_created_at", table_name="customers")
    op.drop_index("ix_download_records_downloaded_at", table_name="download_records")
    op.drop_index("ix_download_records_customer_downloaded", table_name="download_records")
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_orders_created_at", table_name="orders")
    op.drop_index("ix_orders_payment_status_created", table_name="orders")
    op.drop_index("ix_sales_active_window", table_name="sales", postgresql_where=sa.text("is_active"))
    op.drop_index("ix_products_active_category_created", table_name="products")
    op.drop_index(op.f("ix_rate_limit_buckets_updated_at"), table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
