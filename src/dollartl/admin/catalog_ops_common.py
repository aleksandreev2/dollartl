from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dollartl.db.catalog_revision_models import ReleaseRevision, TitleRevision
from dollartl.db.models import AuditLog, Release, Title, TitleAlias
from dollartl.services.catalog_types import normalize_title


class TitleUpdate(BaseModel):
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    english_title: str = Field(min_length=1, max_length=255)
    original_title: str = Field(min_length=1, max_length=255)
    original_language: str = Field(min_length=1, max_length=50)
    description: str = Field(default="", max_length=20_000)
    publication_status: str = Field(pattern=r"^(ongoing|completed|hiatus)$")
    boosty_url: str | None = Field(default=None, max_length=2000)
    aliases: list[str] = Field(default_factory=list, max_length=100)
    expected_updated_at: datetime
    reason: str = Field(min_length=3, max_length=1000)


class ReleaseUpdate(BaseModel):
    chapter_start: int = Field(ge=0)
    chapter_end: int = Field(ge=0)
    display_name: str | None = Field(default=None, max_length=255)
    boosty_url: str | None = Field(default=None, max_length=2000)
    comments_enabled: bool = True
    expected_updated_at: datetime
    reason: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def valid_range(self):
        if self.chapter_end < self.chapter_start:
            raise ValueError("chapter_end must be greater than or equal to chapter_start")
        return self


class PublicationUpdate(BaseModel):
    published: bool
    expected_updated_at: datetime
    reason: str = Field(min_length=3, max_length=1000)


class RollbackRequest(BaseModel):
    expected_updated_at: datetime
    reason: str = Field(min_length=3, max_length=1000)


class FileActivateRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class CleanupRequest(BaseModel):
    dry_run: bool = True
    min_age_days: int = Field(default=30, ge=1, le=3650)
    idempotency_key: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")
    confirmation: str | None = Field(default=None, max_length=120)


class RetryPublicationsRequest(BaseModel):
    publication_ids: list[UUID] = Field(min_length=1, max_length=500)
    dry_run: bool = True
    idempotency_key: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def ensure_not_conflicted(current: datetime | None, expected: datetime) -> None:
    if current is None:
        return
    if abs((aware(current) - aware(expected)).total_seconds()) > 0.001:
        raise HTTPException(
            status_code=409,
            detail="Запись уже изменена в другой сессии. Обновите данные и повторите действие.",
        )


def normalized_aliases(*values: str) -> list[tuple[str, str]]:
    unique: dict[str, str] = {}
    for raw in values:
        alias = raw.strip()
        normalized = normalize_title(alias)
        if alias and normalized:
            unique.setdefault(normalized, alias)
    return sorted(unique.items())


async def title_snapshot(session: AsyncSession, title: Title) -> dict[str, Any]:
    aliases = list(
        (
            await session.execute(
                select(TitleAlias.alias)
                .where(TitleAlias.title_id == title.id)
                .order_by(TitleAlias.alias.asc())
            )
        ).scalars()
    )
    return {
        "slug": title.slug,
        "english_title": title.english_title,
        "original_title": title.original_title,
        "original_language": title.original_language,
        "description": title.description,
        "publication_status": title.publication_status,
        "cover_object_key": title.cover_object_key,
        "cover_content_type": title.cover_content_type,
        "boosty_url": title.boosty_url,
        "is_published": title.is_published,
        "published_at": iso(title.published_at),
        "latest_chapter": title.latest_chapter,
        "aliases": aliases,
    }


def release_snapshot(release: Release) -> dict[str, Any]:
    return {
        "chapter_start": release.chapter_start,
        "chapter_end": release.chapter_end,
        "display_name": release.display_name,
        "boosty_url": release.boosty_url,
        "is_published": release.is_published,
        "published_at": iso(release.published_at),
        "comments_enabled": release.comments_enabled,
        "validation_status": release.validation_status,
        "validation_message": release.validation_message,
        "detection_report": release.detection_report or {},
    }


async def save_title_revision(
    session: AsyncSession,
    *,
    title: Title,
    actor_id: int,
    reason: str,
) -> TitleRevision:
    latest = int(
        (
            await session.execute(
                select(func.coalesce(func.max(TitleRevision.revision), 0)).where(
                    TitleRevision.title_id == title.id
                )
            )
        ).scalar_one()
    )
    revision = TitleRevision(
        title_id=title.id,
        revision=latest + 1,
        snapshot=await title_snapshot(session, title),
        reason=reason.strip(),
        actor_telegram_id=actor_id,
    )
    session.add(revision)
    await session.flush()
    return revision


async def save_release_revision(
    session: AsyncSession,
    *,
    release: Release,
    actor_id: int,
    reason: str,
) -> ReleaseRevision:
    latest = int(
        (
            await session.execute(
                select(func.coalesce(func.max(ReleaseRevision.revision), 0)).where(
                    ReleaseRevision.release_id == release.id
                )
            )
        ).scalar_one()
    )
    revision = ReleaseRevision(
        release_id=release.id,
        revision=latest + 1,
        snapshot=release_snapshot(release),
        reason=reason.strip(),
        actor_telegram_id=actor_id,
    )
    session.add(revision)
    await session.flush()
    return revision


def audit(
    *,
    actor_id: int,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> AuditLog:
    return AuditLog(
        actor_telegram_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
        correlation_id=correlation_id,
    )
