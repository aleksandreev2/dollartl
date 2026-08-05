from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dollartl.db.base import Base, UUIDPrimaryKeyMixin


class TitleRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "title_revisions"
    __table_args__ = (
        UniqueConstraint("title_id", "revision", name="uq_title_revisions_title_revision"),
    )

    title_id: Mapped[UUID] = mapped_column(
        ForeignKey("titles.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    reason: Mapped[str] = mapped_column(Text)
    actor_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class ReleaseRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "release_revisions"
    __table_args__ = (
        UniqueConstraint("release_id", "revision", name="uq_release_revisions_release_revision"),
    )

    release_id: Mapped[UUID] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    reason: Mapped[str] = mapped_column(Text)
    actor_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class FileVersionInspection(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "file_version_inspections"

    file_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("file_versions.id", ondelete="CASCADE"), unique=True, index=True
    )
    inspection: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
