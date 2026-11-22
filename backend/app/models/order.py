import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import DownloadStatus, OrderPaymentStatus, OrderStatus, PaymentStatus
from app.models.mixins import TimestampMixin, created_at_col, enum_col, uuid_pk

if TYPE_CHECKING:
    from app.models.catalog import Product
    from app.models.customer import Customer
    from app.models.seller import SellerProfile


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = uuid_pk()
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    order_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    subtotal_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00")
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00")
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'INR'"))
    status: Mapped[OrderStatus] = mapped_column(
        enum_col(OrderStatus, "order_status"),
        nullable=False,
        default=OrderStatus.PENDING,
        server_default=OrderStatus.PENDING.value,
    )
    payment_status: Mapped[OrderPaymentStatus] = mapped_column(
        enum_col(OrderPaymentStatus, "order_payment_status"),
        nullable=False,
        default=OrderPaymentStatus.UNPAID,
        server_default=OrderPaymentStatus.UNPAID.value,
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(120))
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fulfilled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    customer: Mapped["Customer"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", passive_deletes=True
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="order")
    downloads: Mapped[list["DownloadRecord"]] = relationship(back_populates="order")

    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="total_non_negative"),
        CheckConstraint("subtotal_amount >= 0", name="subtotal_non_negative"),
        CheckConstraint("discount_amount >= 0", name="discount_non_negative"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_iso4217"),
        Index("ix_orders_customer_created", "customer_id", "created_at"),
        Index("ix_orders_status", "status", "payment_status"),
        Index("ix_orders_payment_status_created", "payment_status", "created_at"),
        Index("ix_orders_created_at", "created_at"),
        Index(
            "uq_orders_customer_idempotency_key",
            "customer_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )


class OrderItem(Base):
    """Line item with immutable price, product, and seller snapshots taken at purchase time."""

    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    seller_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("seller_profiles.id", ondelete="SET NULL"), index=True
    )
    seller_store_name_snapshot: Mapped[str] = mapped_column(
        String(150), nullable=False, server_default=text("'DIGI-VERSE Official'")
    )
    seller_store_slug_snapshot: Mapped[Optional[str]] = mapped_column(String(160))
    product_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    original_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    commission_rate_snapshot: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    commission_amount_snapshot: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    gross_amount_snapshot: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    net_amount_snapshot: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    commission_currency_snapshot: Mapped[Optional[str]] = mapped_column(String(3))
    commission_source_snapshot: Mapped[Optional[str]] = mapped_column(String(32))
    commission_snapshotted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Optional["Product"]] = relationship()
    seller: Mapped[Optional["SellerProfile"]] = relationship()

    __table_args__ = (
        UniqueConstraint("order_id", "product_id"),
        CheckConstraint("quantity >= 1", name="quantity_positive"),
        CheckConstraint("purchase_price >= 0", name="purchase_price_non_negative"),
        CheckConstraint("original_price_snapshot >= 0", name="original_price_non_negative"),
        Index("ix_order_items_seller_order", "seller_id", "order_id"),
    )


class Payment(TimestampMixin, Base):
    """Gateway payment attempts. Stores references only: never secrets, card data or UPI PINs."""

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    gateway_name: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'razorpay'"))
    gateway_order_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    gateway_payment_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    gateway_signature: Mapped[Optional[str]] = mapped_column(String(255))
    refund_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'INR'"))
    status: Mapped[PaymentStatus] = mapped_column(
        enum_col(PaymentStatus, "payment_status"),
        nullable=False,
        default=PaymentStatus.CREATED,
        server_default=PaymentStatus.CREATED.value,
    )
    payment_method: Mapped[Optional[str]] = mapped_column(String(30))
    failure_reason: Mapped[Optional[str]] = mapped_column(String(500))
    provider_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    is_signature_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    order: Mapped[Order] = relationship(back_populates="payments")
    customer: Mapped["Customer"] = relationship(back_populates="payments")

    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_iso4217"),
        CheckConstraint(
            "status <> 'captured' OR is_signature_verified", name="captured_requires_verification"
        ),
        # Duplicate-fulfilment guard: at most one captured payment per order.
        Index(
            "uq_payments_one_captured_per_order",
            "order_id",
            unique=True,
            postgresql_where=text("status = 'captured'"),
        ),
        Index("ix_payments_status", "status"),
    )


class DownloadRecord(Base):
    __tablename__ = "download_records"

    id: Mapped[uuid.UUID] = uuid_pk()
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    order_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("order_items.id", ondelete="SET NULL"), index=True
    )
    downloaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[DownloadStatus] = mapped_column(enum_col(DownloadStatus, "download_status"), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64))
    user_agent: Mapped[Optional[str]] = mapped_column(String(512))

    customer: Mapped["Customer"] = relationship(back_populates="downloads")
    product: Mapped[Optional["Product"]] = relationship()
    order: Mapped[Order] = relationship(back_populates="downloads")

    __table_args__ = (
        Index("ix_download_records_customer_product", "customer_id", "product_id"),
        Index("ix_download_records_customer_downloaded", "customer_id", "downloaded_at"),
        Index("ix_download_records_downloaded_at", "downloaded_at"),
    )


class PaymentWebhookEvent(Base):
    """Idempotency ledger of processed gateway webhook events."""

    __tablename__ = "payment_webhook_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    gateway_name: Mapped[str] = mapped_column(String(30), nullable=False)
    event_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    gateway_order_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    gateway_payment_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    processed_at: Mapped[datetime] = created_at_col()
