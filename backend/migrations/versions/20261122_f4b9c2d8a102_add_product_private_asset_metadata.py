"""add_product_private_asset_metadata

Revision ID: f4b9c2d8a102
Revises: e1a7f3c9d201
Create Date: 2026-11-22 08:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f4b9c2d8a102"
down_revision: Union[str, None] = "e1a7f3c9d201"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("asset_storage_backend", sa.String(length=32), nullable=True))
    op.add_column("products", sa.Column("asset_storage_key", sa.String(length=512), nullable=True))
    op.add_column("products", sa.Column("asset_original_filename", sa.String(length=255), nullable=True))
    op.add_column("products", sa.Column("asset_content_type", sa.String(length=120), nullable=True))
    op.add_column("products", sa.Column("asset_size_bytes", sa.BigInteger(), nullable=True))
    op.add_column("products", sa.Column("asset_sha256", sa.String(length=64), nullable=True))
    op.add_column("products", sa.Column("asset_uploaded_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "asset_uploaded_at")
    op.drop_column("products", "asset_sha256")
    op.drop_column("products", "asset_size_bytes")
    op.drop_column("products", "asset_content_type")
    op.drop_column("products", "asset_original_filename")
    op.drop_column("products", "asset_storage_key")
    op.drop_column("products", "asset_storage_backend")
