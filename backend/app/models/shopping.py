import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, created_at_col, uuid_pk

if TYPE_CHECKING:
    from app.models.catalog import Product
    from app.models.customer import Customer


class Wishlist(Base):
    __tablename__ = "wishlists"

    id: Mapped[uuid.UUID] = uuid_pk()
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = created_at_col()

    customer: Mapped["Customer"] = relationship(back_populates="wishlist_items")
    product: Mapped["Product"] = relationship()

    __table_args__ = (UniqueConstraint("customer_id", "product_id"),)


class Cart(TimestampMixin, Base):
    """One persistent cart per customer."""

    __tablename__ = "carts"

    id: Mapped[uuid.UUID] = uuid_pk()
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    customer: Mapped["Customer"] = relationship(back_populates="cart")
    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart", cascade="all, delete-orphan", passive_deletes=True
    )


class CartItem(TimestampMixin, Base):
    __tablename__ = "cart_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    cart_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))

    cart: Mapped[Cart] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()

    __table_args__ = (
        UniqueConstraint("cart_id", "product_id"),
        CheckConstraint("quantity BETWEEN 1 AND 100", name="quantity_range"),
    )
