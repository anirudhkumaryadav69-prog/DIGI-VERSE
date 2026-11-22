import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ProductApprovalStatus
from app.models.mixins import TimestampMixin, created_at_col, enum_col, uuid_pk

if TYPE_CHECKING:
    from app.models.admin import Admin
    from app.models.seller import SellerProfile


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(140), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    products: Mapped[list["Product"]] = relationship(back_populates="category")

    __table_args__ = (
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="slug_format"),
    )


Index("uq_categories_name_lower", func.lower(Category.name), unique=True)


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True)
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Ownership: NULL designates platform-owned official/legacy products; non-NULL belongs to a seller.
    seller_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("seller_profiles.id", ondelete="RESTRICT"), index=True
    )
    approval_status: Mapped[ProductApprovalStatus] = mapped_column(
        enum_col(ProductApprovalStatus, "product_approval_status"),
        nullable=False,
        default=ProductApprovalStatus.PUBLISHED,
        server_default=ProductApprovalStatus.PUBLISHED.value,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)
    submitted_for_review_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reviewed_by_admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("admins.id", ondelete="SET NULL")
    )
    image_url: Mapped[Optional[str]] = mapped_column(String(1024))
    short_description: Mapped[Optional[str]] = mapped_column(String(500))
    main_description: Mapped[Optional[str]] = mapped_column(Text)
    detailed_description: Mapped[Optional[str]] = mapped_column(Text)
    original_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    product_type: Mapped[Optional[str]] = mapped_column(String(80))
    product_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB)
    is_on_sale: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    # SECURITY: private delivery link / managed asset metadata. Never serialise in public API
    # schemas; only stream to verified purchasers via the authorized download endpoint.
    private_download_url: Mapped[Optional[str]] = mapped_column(String(2048))
    asset_storage_backend: Mapped[Optional[str]] = mapped_column(String(32))
    asset_storage_key: Mapped[Optional[str]] = mapped_column(String(512))
    asset_original_filename: Mapped[Optional[str]] = mapped_column(String(255))
    asset_content_type: Mapped[Optional[str]] = mapped_column(String(120))
    asset_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    asset_sha256: Mapped[Optional[str]] = mapped_column(String(64))
    asset_uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    category: Mapped[Category] = relationship(back_populates="products")
    seller: Mapped[Optional["SellerProfile"]] = relationship(back_populates="products")
    reviewed_by_admin: Mapped[Optional["Admin"]] = relationship()
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProductImage.display_order",
    )
    sales: Mapped[list["Sale"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("original_price >= 0", name="original_price_non_negative"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="slug_format"),
        Index("ix_products_active_category", "is_active", "category_id"),
        Index("ix_products_active_category_created", "is_active", "category_id", "created_at"),
        Index("ix_products_seller_status", "seller_id", "approval_status", "is_active"),
        Index("ix_products_created_at", "created_at"),
        Index("ix_products_original_price", "original_price"),
    )

    def __repr__(self) -> str:
        return f"<Product {self.slug}>"


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[uuid.UUID] = uuid_pk()
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    product: Mapped[Product] = relationship(back_populates="images")

    __table_args__ = (
        UniqueConstraint("product_id", "display_order"),
        CheckConstraint("display_order >= 0", name="display_order_non_negative"),
    )


class Sale(Base):
    """Historical and current discounts. At most one active sale per product."""

    __tablename__ = "sales"

    id: Mapped[uuid.UUID] = uuid_pk()
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discounted_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = created_at_col()

    product: Mapped[Product] = relationship(back_populates="sales")

    __table_args__ = (
        CheckConstraint("discounted_price >= 0", name="discounted_price_non_negative"),
        CheckConstraint("discounted_price < original_price_snapshot", name="discount_below_original"),
        CheckConstraint("expires_at > starts_at", name="expiry_after_start"),
        Index(
            "uq_sales_one_active_per_product",
            "product_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "ix_sales_active_window",
            "product_id",
            "starts_at",
            "expires_at",
            postgresql_where=text("is_active"),
        ),
    )
