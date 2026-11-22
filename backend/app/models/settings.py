import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import updated_at_col, uuid_pk


class StoreSetting(Base):
    """Non-secret store configuration. API keys/secrets belong in environment variables only."""

    __tablename__ = "store_settings"

    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        CheckConstraint("key ~ '^[a-z0-9_.]+$'", name="key_format"),
    )
