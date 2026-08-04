from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dollartl.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SuggestionRuleConsent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "suggestion_rule_consents"
    __table_args__ = (
        UniqueConstraint("user_id", "version", name="uq_suggestion_rule_consents_user_version"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, index=True)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TitleSuggestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "title_suggestions"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    original_title: Mapped[str | None] = mapped_column(String(500), index=True)
    normalized_title: Mapped[str | None] = mapped_column(String(500), index=True)
    detected_language: Mapped[str | None] = mapped_column(String(80), index=True)
    chapter_count: Mapped[int | None] = mapped_column(Integer)
    publication_status: Mapped[str | None] = mapped_column(String(30), index=True)
    requested_chapter_start: Mapped[int] = mapped_column(Integer, default=1)
    requested_chapter_end: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    vip_snapshot: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    public_reason: Mapped[str | None] = mapped_column(Text)
    internal_note: Mapped[str | None] = mapped_column(Text)
    linked_title_id: Mapped[UUID | None] = mapped_column(ForeignKey("titles.id", ondelete="SET NULL"), index=True)
    duplicate_review_required: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SuggestionSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "suggestion_sources"
    __table_args__ = (
        UniqueConstraint("suggestion_id", "normalized_url", name="uq_suggestion_sources_suggestion_url"),
    )

    suggestion_id: Mapped[UUID] = mapped_column(ForeignKey("title_suggestions.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(Text)
    normalized_url: Mapped[str] = mapped_column(Text, index=True)
    source_order: Mapped[int] = mapped_column(Integer, default=0)


class SuggestionFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "suggestion_files"
    __table_args__ = (
        UniqueConstraint("suggestion_id", "file_kind", name="uq_suggestion_files_suggestion_kind"),
    )

    suggestion_id: Mapped[UUID] = mapped_column(ForeignKey("title_suggestions.id", ondelete="CASCADE"), index=True)
    file_kind: Mapped[str] = mapped_column(String(20), index=True)
    object_key: Mapped[str] = mapped_column(String(700), unique=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    telegram_file_id: Mapped[str | None] = mapped_column(String(500))
    telegram_file_unique_id: Mapped[str | None] = mapped_column(String(255), index=True)
    validation_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    validation_message: Mapped[str | None] = mapped_column(Text)
    inspection: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class SuggestionStatusHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "suggestion_status_history"

    suggestion_id: Mapped[UUID] = mapped_column(ForeignKey("title_suggestions.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30), index=True)
    public_reason: Mapped[str | None] = mapped_column(Text)
    internal_note: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    actor_admin_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class SuggestionQuotaUsage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "suggestion_quota_usage"
    __table_args__ = (
        UniqueConstraint("suggestion_id", name="uq_suggestion_quota_usage_suggestion"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    suggestion_id: Mapped[UUID] = mapped_column(ForeignKey("title_suggestions.id", ondelete="CASCADE"), index=True)
    quota_month: Mapped[date] = mapped_column(Date, index=True)
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    restored_by_admin_id: Mapped[int | None] = mapped_column(BigInteger)
    restore_reason: Mapped[str | None] = mapped_column(Text)


class DuplicateCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "duplicate_candidates"

    suggestion_id: Mapped[UUID] = mapped_column(ForeignKey("title_suggestions.id", ondelete="CASCADE"), index=True)
    candidate_type: Mapped[str] = mapped_column(String(30), index=True)
    candidate_suggestion_id: Mapped[UUID | None] = mapped_column(ForeignKey("title_suggestions.id", ondelete="CASCADE"), index=True)
    candidate_title_id: Mapped[UUID | None] = mapped_column(ForeignKey("titles.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer, default=100)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    resolution: Mapped[str | None] = mapped_column(String(40))
    resolved_by_admin_id: Mapped[int | None] = mapped_column(BigInteger)
