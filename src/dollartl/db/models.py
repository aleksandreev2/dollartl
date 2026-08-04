from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dollartl.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SystemSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    description: Mapped[str | None] = mapped_column(Text)


class SchemaMetadata(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "schema_metadata"

    component: Mapped[str] = mapped_column(String(100), unique=True)
    version: Mapped[str] = mapped_column(String(100))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_log"

    actor_telegram_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(150), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(100), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(100), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    correlation_id: Mapped[str | None] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class BackgroundJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "background_jobs"

    job_type: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True, default="pending")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    run_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_error: Mapped[str | None] = mapped_column(Text)


class OutboxEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "outbox_events"

    topic: Mapped[str] = mapped_column(String(120), index=True)
    aggregate_type: Mapped[str] = mapped_column(String(100), index=True)
    aggregate_id: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64), index=True)
    telegram_first_name: Mapped[str | None] = mapped_column(String(255))
    telegram_last_name: Mapped[str | None] = mapped_column(String(255))
    anonymous_id: Mapped[int] = mapped_column(
        BigInteger, Identity(start=1000), unique=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    @property
    def anonymous_name(self) -> str:
        return f"Anonymous {self.anonymous_id}"


class UserConsent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_consents"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "consent_type", "version", name="uq_user_consents_user_type_version"
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    consent_type: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[int] = mapped_column(Integer)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    source: Mapped[str] = mapped_column(String(40), default="telegram_bot")


class UserSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_settings"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    display_name: Mapped[str | None] = mapped_column(String(24))
    locale: Mapped[str] = mapped_column(String(10), default="en")


class NotificationPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    new_title_announcements: Mapped[bool] = mapped_column(Boolean, default=True)
    service_notifications: Mapped[bool] = mapped_column(Boolean, default=True)


class Ban(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bans"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    ban_type: Mapped[str] = mapped_column(String(20), index=True)
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    public_reason: Mapped[str] = mapped_column(Text)
    reason_template: Mapped[str | None] = mapped_column(String(80))
    internal_note: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_admin_id: Mapped[int] = mapped_column(BigInteger)
    last_notice_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unbanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unbanned_by_admin_id: Mapped[int | None] = mapped_column(BigInteger)


class BanHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ban_history"

    ban_id: Mapped[UUID] = mapped_column(
        ForeignKey("bans.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(50), index=True)
    actor_telegram_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
