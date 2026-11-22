"""phase9_multivendor_sellers

Revision ID: c9d0e1f2a345
Revises: b8c9d0e1f234
Create Date: 2026-11-22 10:15:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a345"
down_revision: Union[str, None] = "b8c9d0e1f234"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create seller_profiles table linked 1:1 with customers
    op.create_table(
        "seller_profiles",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("store_name", sa.String(length=150), nullable=False),
        sa.Column("store_slug", sa.String(length=160), nullable=False),
        sa.Column("seller_display_name", sa.String(length=150), nullable=False),
        sa.Column("store_description", sa.Text(), nullable=True),
        sa.Column("application_description", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.String(length=1024), nullable=True),
        sa.Column("banner_url", sa.String(length=1024), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=False),
        sa.Column("contact_info", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("business_type", sa.String(length=80), nullable=False),
        sa.Column("product_categories", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "application_status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("suspension_reason", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_admin_id", sa.Uuid(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_seller_profiles_customer_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approved_by_admin_id"], ["admins.id"], name="fk_seller_profiles_approved_by", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id", name="uq_seller_profiles_customer_id"),
        sa.UniqueConstraint("store_slug", name="uq_seller_profiles_store_slug"),
        sa.CheckConstraint("store_slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="store_slug_format"),
        sa.CheckConstraint(
            "application_status IN ('pending', 'approved', 'rejected', 'suspended')",
            name="seller_application_status",
        ),
    )
    op.create_index("ix_seller_profiles_status", "seller_profiles", ["application_status"])
    op.create_index("ix_seller_profiles_created_at", "seller_profiles", ["created_at"])

    # 2. Extend products with nullable seller_id (NULL = platform-owned legacy) and approval workflow
    op.add_column("products", sa.Column("seller_id", sa.Uuid(), nullable=True))
    op.add_column(
        "products",
        sa.Column(
            "approval_status",
            sa.String(length=32),
            server_default=sa.text("'published'"),
            nullable=False,
        ),
    )
    op.add_column("products", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("submitted_for_review_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("products", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("products", sa.Column("reviewed_by_admin_id", sa.Uuid(), nullable=True))

    op.create_foreign_key(
        "fk_products_seller_id",
        "products",
        "seller_profiles",
        ["seller_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_products_reviewed_by_admin_id",
        "products",
        "admins",
        ["reviewed_by_admin_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "product_approval_status",
        "products",
        "approval_status IN ('draft', 'pending_review', 'published', 'rejected', 'archived')",
    )
    op.create_index("ix_products_seller_id", "products", ["seller_id"])
    op.create_index(
        "ix_products_seller_status",
        "products",
        ["seller_id", "approval_status", "is_active"],
    )

    # 3. Extend order_items with seller attribution + immutable store snapshots
    op.add_column("order_items", sa.Column("seller_id", sa.Uuid(), nullable=True))
    op.add_column(
        "order_items",
        sa.Column(
            "seller_store_name_snapshot",
            sa.String(length=150),
            server_default=sa.text("'DIGI-VERSE Official'"),
            nullable=False,
        ),
    )
    op.add_column("order_items", sa.Column("seller_store_slug_snapshot", sa.String(length=160), nullable=True))
    op.create_foreign_key(
        "fk_order_items_seller_id",
        "order_items",
        "seller_profiles",
        ["seller_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_order_items_seller_id", "order_items", ["seller_id"])
    op.create_index("ix_order_items_seller_order", "order_items", ["seller_id", "order_id"])


def downgrade() -> None:
    op.drop_index("ix_order_items_seller_order", table_name="order_items")
    op.drop_index("ix_order_items_seller_id", table_name="order_items")
    op.drop_constraint("fk_order_items_seller_id", "order_items", type_="foreignkey")
    op.drop_column("order_items", "seller_store_slug_snapshot")
    op.drop_column("order_items", "seller_store_name_snapshot")
    op.drop_column("order_items", "seller_id")

    op.drop_index("ix_products_seller_status", table_name="products")
    op.drop_index("ix_products_seller_id", table_name="products")
    op.drop_constraint("product_approval_status", "products", type_="check")
    op.drop_constraint("fk_products_reviewed_by_admin_id", "products", type_="foreignkey")
    op.drop_constraint("fk_products_seller_id", "products", type_="foreignkey")
    op.drop_column("products", "reviewed_by_admin_id")
    op.drop_column("products", "reviewed_at")
    op.drop_column("products", "submitted_for_review_at")
    op.drop_column("products", "rejection_reason")
    op.drop_column("products", "approval_status")
    op.drop_column("products", "seller_id")

    op.drop_index("ix_seller_profiles_created_at", table_name="seller_profiles")
    op.drop_index("ix_seller_profiles_status", table_name="seller_profiles")
    op.drop_table("seller_profiles")
