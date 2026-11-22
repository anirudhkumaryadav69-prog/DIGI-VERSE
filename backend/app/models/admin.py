import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, created_at_col, uuid_pk

if TYPE_CHECKING:
    from app.models.auth import AuthSession


class Admin(TimestampMixin, Base):
    """Store administrators. Kept in a separate table from customers (privilege separation)."""

    __tablename__ = "admins"

    id: Mapped[uuid.UUID] = uuid_pk()
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="admin", passive_deletes=True)
    sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="admin", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("failed_login_attempts >= 0", name="failed_attempts_non_negative"),
    )

    def __repr__(self) -> str:
        return f"<Admin {self.username}>"


# Case-insensitive uniqueness for admin emails.
Index("uq_admins_email_lower", func.lower(Admin.email), unique=True)


class AuditLog(Base):
    """Immutable record of administrative actions."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = uuid_pk()
    admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("admins.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(100))
    details: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = created_at_col()

    admin: Mapped[Optional[Admin]] = relationship(back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )
