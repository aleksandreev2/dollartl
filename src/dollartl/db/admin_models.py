from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dollartl.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Broadcast(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "broadcasts"
    __table_args__ = (
        CheckConstraint("status IN ('draft','scheduled','processing','completed','failed','cancelled')", name="broadcasts_status"),
        CheckConstraint("audience_type IN ('all','active_vip','vip_grace','standard','title_followers','selected')", name="broadcasts_audience_type"),
    )

    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    audience_type: Mapped[str] = mapped_column(String(30), index=True)
    title_id: Mapped[UUID | None] = mapped_column(ForeignKey("titles.id", ondelete="SET NULL"), index=True)
    text: Mapped[str] = mapped_column(Text)
    photo_object_key: Mapped[str | None] = mapped_column(String(500))
    photo_content_type: Mapped[str | None] = mapped_column(String(120))
    button_text: Mapped[str | None] = mapped_column(String(64))
    button_url: Mapped[str | None] = mapped_column(Text)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    selected_user_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_by_admin_id: Mapped[int] = mapped_column(BigInteger)


class BroadcastRecipient(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "broadcast_recipients"
    __table_args__ = (
        UniqueConstraint("broadcast_id", "user_id", name="uq_broadcast_recipients_broadcast_user"),
        CheckConstraint("status IN ('pending','sent','failed','skipped')", name="broadcast_recipients_status"),
    )

    broadcast_id: Mapped[UUID] = mapped_column(ForeignKey("broadcasts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    last_error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class AdminUpload(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "admin_uploads"

    object_key: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    purpose: Mapped[str] = mapped_column(String(50), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_by_admin_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
