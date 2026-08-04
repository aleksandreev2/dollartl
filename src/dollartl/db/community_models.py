from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dollartl.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Comment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "comments"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    target_type: Mapped[str] = mapped_column(String(20), index=True)
    title_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("titles.id", ondelete="CASCADE"), index=True
    )
    release_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"), index=True
    )
    original_body: Mapped[str] = mapped_column(Text)
    public_body: Mapped[str] = mapped_column(Text)
    replacement_count: Mapped[int] = mapped_column(Integer, default=0)
    vip_snapshot: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_admin_id: Mapped[int | None] = mapped_column(BigInteger)


class CommentRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "comment_revisions"

    comment_id: Mapped[UUID] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), index=True
    )
    original_body: Mapped[str] = mapped_column(Text)
    public_body: Mapped[str] = mapped_column(Text)
    replacement_count: Mapped[int] = mapped_column(Integer, default=0)
    editor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    editor_admin_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class ModerationRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "moderation_rules"

    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    pattern: Mapped[str] = mapped_column(Text)
    replacement: Mapped[str] = mapped_column(String(40), default="***")
    applies_to_comments: Mapped[bool] = mapped_column(Boolean, default=True)
    applies_to_nicknames: Mapped[bool] = mapped_column(Boolean, default=True)
    applies_to_feedback: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class ModerationAllowlist(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "moderation_allowlist"

    normalized_value: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    note: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class ModerationMatch(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "moderation_matches"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    rule_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("moderation_rules.id", ondelete="SET NULL"), index=True
    )
    surface: Mapped[str] = mapped_column(String(30), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(30), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(100), index=True)
    matched_hash: Mapped[str] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class TranslationRating(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "translation_ratings"
    __table_args__ = (
        UniqueConstraint("user_id", "release_id", name="uq_translation_ratings_user_release"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    release_id: Mapped[UUID] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[int] = mapped_column(Integer, index=True)
    feedback: Mapped[str] = mapped_column(Text)
    vip_snapshot: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="new", index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class TranslationRatingCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "translation_rating_categories"

    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class TranslationRatingCategoryLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "translation_rating_category_links"
    __table_args__ = (
        UniqueConstraint(
            "rating_id", "category_id", name="uq_translation_rating_category_link"
        ),
    )

    rating_id: Mapped[UUID] = mapped_column(
        ForeignKey("translation_ratings.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("translation_rating_categories.id", ondelete="CASCADE"), index=True
    )


class TranslationRatingRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "translation_rating_revisions"

    rating_id: Mapped[UUID] = mapped_column(
        ForeignKey("translation_ratings.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[int] = mapped_column(Integer)
    feedback: Mapped[str] = mapped_column(Text)
    category_codes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    vip_snapshot: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class TranslationRatingStatusHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "translation_rating_status_history"

    rating_id: Mapped[UUID] = mapped_column(
        ForeignKey("translation_ratings.id", ondelete="CASCADE"), index=True
    )
    old_status: Mapped[str | None] = mapped_column(String(30))
    new_status: Mapped[str] = mapped_column(String(30), index=True)
    admin_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class Report(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reports"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    target_type: Mapped[str] = mapped_column(String(20), index=True)
    title_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("titles.id", ondelete="CASCADE"), index=True
    )
    release_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    description: Mapped[str] = mapped_column(Text)
    assigned_admin_id: Mapped[int | None] = mapped_column(BigInteger)


class ReportMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "report_messages"

    report_id: Mapped[UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    sender_type: Mapped[str] = mapped_column(String(20), index=True)
    sender_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    sender_admin_id: Mapped[int | None] = mapped_column(BigInteger)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class ReportAttachment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "report_attachments"

    report_id: Mapped[UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    report_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("report_messages.id", ondelete="CASCADE"), index=True
    )
    telegram_file_id: Mapped[str] = mapped_column(String(500))
    telegram_file_unique_id: Mapped[str | None] = mapped_column(String(255), index=True)
    filename: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
