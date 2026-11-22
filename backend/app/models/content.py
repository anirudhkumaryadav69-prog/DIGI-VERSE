import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import AdDisplayPosition
from app.models.mixins import TimestampMixin, enum_col, uuid_pk


class Banner(TimestampMixin, Base):
    __tablename__ = "banners"

    id: Mapped[uuid.UUID] = uuid_pk()
    heading: Mapped[str] = mapped_column(String(200), nullable=False)
    subtitle: Mapped[Optional[str]] = mapped_column(String(300))
    promotional_text: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    cta_text: Mapped[Optional[str]] = mapped_column(String(60))
    cta_destination: Mapped[Optional[str]] = mapped_column(String(1024))
    display_priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at", name="end_after_start"
        ),
        Index("ix_banners_active_priority", "is_active", "display_priority"),
    )


class AdvertisementVideo(TimestampMixin, Base):
    __tablename__ = "advertisement_videos"

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    video_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1024))
    destination_url: Mapped[Optional[str]] = mapped_column(String(1024))
    display_position: Mapped[AdDisplayPosition] = mapped_column(
        enum_col(AdDisplayPosition, "ad_display_position"), nullable=False
    )
    display_priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (
        Index("ix_advertisement_videos_position_priority", "display_position", "is_active", "display_priority"),
    )
