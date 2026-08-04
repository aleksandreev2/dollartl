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
    manual_download_access: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
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
    pending_deep_link_token: Mapped[str | None] = mapped_column(String(64), index=True)


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


class Title(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "titles"

    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    english_title: Mapped[str] = mapped_column(String(255), index=True)
    original_title: Mapped[str] = mapped_column(String(255), index=True)
    original_language: Mapped[str] = mapped_column(String(50), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    publication_status: Mapped[str] = mapped_column(String(20), default="ongoing", index=True)
    cover_object_key: Mapped[str | None] = mapped_column(String(500))
    cover_content_type: Mapped[str | None] = mapped_column(String(100))
    boosty_url: Mapped[str | None] = mapped_column(Text)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    latest_chapter: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_by_admin_id: Mapped[int] = mapped_column(BigInteger)


class TitleAlias(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "title_aliases"
    __table_args__ = (
        UniqueConstraint("title_id", "normalized_alias", name="uq_title_aliases_title_alias"),
    )

    title_id: Mapped[UUID] = mapped_column(
        ForeignKey("titles.id", ondelete="CASCADE"), index=True
    )
    alias: Mapped[str] = mapped_column(String(255), index=True)
    normalized_alias: Mapped[str] = mapped_column(String(255), index=True)


class Release(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "releases"
    __table_args__ = (
        UniqueConstraint(
            "title_id", "chapter_start", "chapter_end", name="uq_releases_title_range"
        ),
    )

    title_id: Mapped[UUID] = mapped_column(
        ForeignKey("titles.id", ondelete="CASCADE"), index=True
    )
    chapter_start: Mapped[int] = mapped_column(Integer, index=True)
    chapter_end: Mapped[int] = mapped_column(Integer, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    boosty_url: Mapped[str | None] = mapped_column(Text)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    comments_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    validation_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    validation_message: Mapped[str | None] = mapped_column(Text)
    detection_report: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_by_admin_id: Mapped[int] = mapped_column(BigInteger)

    @property
    def chapter_label(self) -> str:
        return self.display_name or f"Chapters {self.chapter_start}–{self.chapter_end}"


class ReleaseFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "release_files"
    __table_args__ = (
        UniqueConstraint("release_id", "file_kind", name="uq_release_files_release_kind"),
    )

    release_id: Mapped[UUID] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"), index=True
    )
    file_kind: Mapped[str] = mapped_column(String(10), index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=0)


class FileVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "file_versions"
    __table_args__ = (
        UniqueConstraint(
            "release_file_id", "version", name="uq_file_versions_release_file_version"
        ),
    )

    release_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("release_files.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    object_key: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    telegram_file_id: Mapped[str | None] = mapped_column(String(500))
    telegram_file_unique_id: Mapped[str | None] = mapped_column(String(255), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_admin_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class UserTitleFollow(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_title_follows"
    __table_args__ = (
        UniqueConstraint("user_id", "title_id", name="uq_user_title_follows_user_title"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title_id: Mapped[UUID] = mapped_column(
        ForeignKey("titles.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class DeepLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "deep_links"

    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    target_type: Mapped[str] = mapped_column(String(20), index=True)
    title_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("titles.id", ondelete="CASCADE"), index=True
    )
    release_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"), index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    uses: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class ChannelPublication(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "channel_publications"
    __table_args__ = (
        UniqueConstraint(
            "target_type", "target_id", name="uq_channel_publications_target"
        ),
    )

    target_type: Mapped[str] = mapped_column(String(20), index=True)
    target_id: Mapped[str] = mapped_column(String(100), index=True)
    telegram_chat_id: Mapped[str] = mapped_column(String(100))
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    error: Mapped[str | None] = mapped_column(Text)


class DownloadEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "download_events"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    release_id: Mapped[UUID] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"), index=True
    )
    file_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("file_versions.id", ondelete="SET NULL"), index=True
    )
    delivery_method: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class OutboxDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "outbox_deliveries"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_outbox_deliveries_event_user"),
    )

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("outbox_events.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    error: Mapped[str | None] = mapped_column(Text)
