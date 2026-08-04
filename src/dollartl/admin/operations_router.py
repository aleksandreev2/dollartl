from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select

from dollartl.admin.auth import AdminPrincipal, require_admin
from dollartl.db.admin_models import Broadcast
from dollartl.db.boosty_models import BoostySyncError
from dollartl.db.community_models import Report, TranslationRating
from dollartl.db.models import (
    AuditLog,
    ChannelPublication,
    FileVersion,
    Release,
    Title,
    User,
    UserSettings,
)
from dollartl.db.resilience_models import BackupRun
from dollartl.db.session import SessionFactory
from dollartl.db.suggestion_models import TitleSuggestion

Admin = Annotated[AdminPrincipal, Depends(require_admin)]
router = APIRouter(tags=["admin-operations"])

_SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}
_NUMERIC_QUERY = re.compile(r"(?:anonymous\s*)?(\d{1,20})$", re.IGNORECASE)


def normalize_query(value: str) -> str:
    return " ".join(value.strip().split())


def numeric_query(value: str) -> int | None:
    match = _NUMERIC_QUERY.fullmatch(normalize_query(value))
    return int(match.group(1)) if match else None


def uuid_query(value: str) -> UUID | None:
    try:
        return UUID(normalize_query(value))
    except ValueError:
        return None


def trim(value: str | None, limit: int = 180) -> str:
    compact = " ".join((value or "").split())
    return compact if len(compact) <= limit else f"{compact[: limit - 1]}…"


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def attention_item(
    *,
    kind: str,
    entity_id: UUID | str,
    severity: str,
    title: str,
    description: str,
    section: str,
    created_at: datetime | None,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": f"{kind}:{entity_id}",
        "kind": kind,
        "entity_id": str(entity_id),
        "severity": severity,
        "title": title,
        "description": trim(description),
        "section": section,
        "status": status,
        "created_at": iso(created_at),
        "metadata": metadata or {},
    }


def search_result(
    *,
    kind: str,
    entity_id: UUID | str,
    title: str,
    subtitle: str,
    section: str,
    created_at: datetime | None,
    status: str | None = None,
    rank: int = 0,
) -> dict[str, Any]:
    return {
        "id": f"{kind}:{entity_id}",
        "kind": kind,
        "entity_id": str(entity_id),
        "title": trim(title, 140),
        "subtitle": trim(subtitle, 220),
        "section": section,
        "status": status,
        "created_at": iso(created_at),
        "rank": rank,
    }


@router.get("/attention")
async def attention_queue(
    admin: Admin,
    limit: int = Query(default=60, ge=1, le=200),
) -> dict[str, Any]:
    del admin
    per_kind = min(max(limit // 4, 8), 30)
    items: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    async with SessionFactory() as session:
        suggestions = (
            await session.execute(
                select(TitleSuggestion, User)
                .join(User, User.id == TitleSuggestion.user_id)
                .where(TitleSuggestion.status == "under_review")
                .order_by(
                    TitleSuggestion.duplicate_review_required.desc(),
                    TitleSuggestion.submitted_at.asc(),
                )
                .limit(per_kind)
            )
        ).all()
        for suggestion, user in suggestions:
            items.append(
                attention_item(
                    kind="suggestion",
                    entity_id=suggestion.id,
                    severity="high" if suggestion.duplicate_review_required else "medium",
                    title=suggestion.original_title or "Untitled suggestion",
                    description=(
                        f"Anonymous {user.anonymous_id} · "
                        f"{suggestion.chapter_count or 'unknown'} chapters"
                    ),
                    section="suggestions",
                    created_at=suggestion.submitted_at or suggestion.created_at,
                    status=suggestion.status,
                    metadata={
                        "anonymous_id": user.anonymous_id,
                        "duplicate_review_required": suggestion.duplicate_review_required,
                    },
                )
            )

        reports = (
            await session.execute(
                select(Report, User)
                .join(User, User.id == Report.user_id)
                .where(Report.status.in_(["open", "in_progress"]))
                .order_by(Report.created_at.asc())
                .limit(per_kind)
            )
        ).all()
        for report, user in reports:
            items.append(
                attention_item(
                    kind="report",
                    entity_id=report.id,
                    severity="high" if report.status == "open" else "medium",
                    title=f"Report: {report.category}",
                    description=f"Anonymous {user.anonymous_id} · {report.description}",
                    section="community",
                    created_at=report.created_at,
                    status=report.status,
                    metadata={"anonymous_id": user.anonymous_id, "target_type": report.target_type},
                )
            )

        ratings = (
            await session.execute(
                select(TranslationRating, Release, User)
                .join(Release, Release.id == TranslationRating.release_id)
                .join(User, User.id == TranslationRating.user_id)
                .where(
                    TranslationRating.status.in_(["new", "in_progress"]),
                    TranslationRating.is_deleted.is_(False),
                )
                .order_by(TranslationRating.score.asc(), TranslationRating.created_at.asc())
                .limit(per_kind)
            )
        ).all()
        for rating, release, user in ratings:
            severity = "high" if rating.score <= 2 else "medium" if rating.score <= 4 else "low"
            items.append(
                attention_item(
                    kind="rating",
                    entity_id=rating.id,
                    severity=severity,
                    title=f"{rating.score}/5 · {release.chapter_label}",
                    description=f"Anonymous {user.anonymous_id} · {rating.feedback}",
                    section="community",
                    created_at=rating.created_at,
                    status=rating.status,
                    metadata={"anonymous_id": user.anonymous_id, "score": rating.score},
                )
            )

        boosty_errors = list(
            (
                await session.execute(
                    select(BoostySyncError)
                    .where(BoostySyncError.created_at >= now - timedelta(days=7))
                    .order_by(BoostySyncError.created_at.desc())
                    .limit(per_kind)
                )
            ).scalars()
        )
        for error in boosty_errors:
            items.append(
                attention_item(
                    kind="boosty_error",
                    entity_id=error.id,
                    severity="high",
                    title=f"Boosty: {error.error_code}",
                    description=error.message,
                    section="boosty",
                    created_at=error.created_at,
                    status="error",
                )
            )

        failed_broadcasts = list(
            (
                await session.execute(
                    select(Broadcast)
                    .where(Broadcast.status == "failed")
                    .order_by(Broadcast.updated_at.desc())
                    .limit(per_kind)
                )
            ).scalars()
        )
        for broadcast in failed_broadcasts:
            items.append(
                attention_item(
                    kind="broadcast",
                    entity_id=broadcast.id,
                    severity="high",
                    title="Broadcast failed",
                    description=(
                        f"{broadcast.failed_count} failed, "
                        f"{broadcast.sent_count}/{broadcast.total_count} sent"
                    ),
                    section="broadcasts",
                    created_at=broadcast.updated_at,
                    status=broadcast.status,
                )
            )

        failed_publications = list(
            (
                await session.execute(
                    select(ChannelPublication)
                    .where(ChannelPublication.status == "failed")
                    .order_by(ChannelPublication.updated_at.desc())
                    .limit(per_kind)
                )
            ).scalars()
        )
        for publication in failed_publications:
            items.append(
                attention_item(
                    kind="channel_publication",
                    entity_id=publication.id,
                    severity="high",
                    title=f"Channel publication failed: {publication.target_type}",
                    description=publication.error or publication.target_id,
                    section="channel",
                    created_at=publication.updated_at,
                    status=publication.status,
                    metadata={"target_id": publication.target_id},
                )
            )

        failed_backups = list(
            (
                await session.execute(
                    select(BackupRun)
                    .where(
                        BackupRun.status == "failed",
                        BackupRun.created_at >= now - timedelta(days=30),
                    )
                    .order_by(BackupRun.created_at.desc())
                    .limit(per_kind)
                )
            ).scalars()
        )
        for backup in failed_backups:
            items.append(
                attention_item(
                    kind="backup",
                    entity_id=backup.id,
                    severity="critical",
                    title="Backup or restore verification failed",
                    description=backup.error or "Backup run failed without a recorded message",
                    section="settings",
                    created_at=backup.completed_at or backup.created_at,
                    status=backup.status,
                )
            )

        invalid_releases = (
            await session.execute(
                select(Release, Title)
                .join(Title, Title.id == Release.title_id)
                .where(Release.validation_status.in_(["error", "warning"]))
                .order_by(Release.updated_at.desc())
                .limit(per_kind)
            )
        ).all()
        for release, title in invalid_releases:
            items.append(
                attention_item(
                    kind="release_validation",
                    entity_id=release.id,
                    severity="high" if release.validation_status == "error" else "medium",
                    title=f"{title.english_title} · {release.chapter_label}",
                    description=release.validation_message or "Release validation needs review",
                    section="catalog",
                    created_at=release.updated_at,
                    status=release.validation_status,
                )
            )

    def sort_key(item: dict[str, Any]) -> tuple[int, float]:
        created = item.get("created_at")
        parsed = datetime.fromisoformat(created) if created else now
        return (_SEVERITY_ORDER.get(item["severity"], 0), parsed.timestamp())

    items.sort(key=sort_key, reverse=True)
    selected = items[:limit]
    counts = {
        severity: sum(1 for item in items if item["severity"] == severity)
        for severity in ("critical", "high", "medium", "low")
    }
    return {"items": selected, "counts": counts, "total": len(items)}


@router.get("/search")
async def global_search(
    admin: Admin,
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    del admin
    query = normalize_query(q)
    pattern = f"%{query}%"
    numeric = numeric_query(query)
    exact_uuid = uuid_query(query)
    per_kind = min(max(limit // 6, 6), 20)
    results: list[dict[str, Any]] = []

    async with SessionFactory() as session:
        titles = list(
            (
                await session.execute(
                    select(Title)
                    .where(
                        or_(
                            Title.english_title.ilike(pattern),
                            Title.original_title.ilike(pattern),
                            Title.slug.ilike(pattern),
                        )
                    )
                    .order_by(Title.updated_at.desc())
                    .limit(per_kind)
                )
            ).scalars()
        )
        for item in titles:
            exact = query.casefold() in {
                item.english_title.casefold(),
                item.original_title.casefold(),
                item.slug.casefold(),
            }
            results.append(
                search_result(
                    kind="title",
                    entity_id=item.id,
                    title=item.english_title,
                    subtitle=f"{item.original_title} · chapter {item.latest_chapter}",
                    section="catalog",
                    created_at=item.updated_at,
                    status="published" if item.is_published else "draft",
                    rank=100 if exact else 70,
                )
            )

        user_clauses = [User.telegram_username.ilike(f"%{query.lstrip('@')}%")]
        if numeric is not None:
            user_clauses.extend([User.telegram_id == numeric, User.anonymous_id == numeric])
        users = (
            await session.execute(
                select(User, UserSettings)
                .outerjoin(UserSettings, UserSettings.user_id == User.id)
                .where(or_(*user_clauses))
                .order_by(User.last_seen_at.desc())
                .limit(per_kind)
            )
        ).all()
        for user, preferences in users:
            exact = numeric in {user.telegram_id, user.anonymous_id} if numeric is not None else False
            results.append(
                search_result(
                    kind="user",
                    entity_id=user.id,
                    title=(preferences.display_name if preferences and preferences.display_name else user.anonymous_name),
                    subtitle=(
                        f"{'@' + user.telegram_username if user.telegram_username else 'no username'}"
                        f" · Telegram {user.telegram_id}"
                    ),
                    section="users",
                    created_at=user.last_seen_at,
                    status="active" if user.is_active else "inactive",
                    rank=110 if exact else 65,
                )
            )

        release_clauses = [
            Release.display_name.ilike(pattern),
            Title.english_title.ilike(pattern),
            Title.original_title.ilike(pattern),
        ]
        if numeric is not None:
            release_clauses.extend(
                [
                    Release.chapter_start == numeric,
                    Release.chapter_end == numeric,
                ]
            )
        releases = (
            await session.execute(
                select(Release, Title)
                .join(Title, Title.id == Release.title_id)
                .where(or_(*release_clauses))
                .order_by(Release.updated_at.desc())
                .limit(per_kind)
            )
        ).all()
        for release, title in releases:
            results.append(
                search_result(
                    kind="release",
                    entity_id=release.id,
                    title=f"{title.english_title} · {release.chapter_label}",
                    subtitle=release.validation_message or f"Chapters {release.chapter_start}–{release.chapter_end}",
                    section="catalog",
                    created_at=release.updated_at,
                    status=release.validation_status,
                    rank=80 if numeric in {release.chapter_start, release.chapter_end} else 60,
                )
            )

        suggestions = (
            await session.execute(
                select(TitleSuggestion, User)
                .join(User, User.id == TitleSuggestion.user_id)
                .where(
                    TitleSuggestion.status != "draft",
                    TitleSuggestion.original_title.ilike(pattern),
                )
                .order_by(TitleSuggestion.updated_at.desc())
                .limit(per_kind)
            )
        ).all()
        for item, user in suggestions:
            results.append(
                search_result(
                    kind="suggestion",
                    entity_id=item.id,
                    title=item.original_title or "Untitled suggestion",
                    subtitle=f"Anonymous {user.anonymous_id} · {item.status}",
                    section="suggestions",
                    created_at=item.updated_at,
                    status=item.status,
                    rank=55,
                )
            )

        reports = (
            await session.execute(
                select(Report, User)
                .join(User, User.id == Report.user_id)
                .where(or_(Report.category.ilike(pattern), Report.description.ilike(pattern)))
                .order_by(Report.updated_at.desc())
                .limit(per_kind)
            )
        ).all()
        for item, user in reports:
            results.append(
                search_result(
                    kind="report",
                    entity_id=item.id,
                    title=f"{item.category} · Anonymous {user.anonymous_id}",
                    subtitle=item.description,
                    section="community",
                    created_at=item.updated_at,
                    status=item.status,
                    rank=50,
                )
            )

        files = list(
            (
                await session.execute(
                    select(FileVersion)
                    .where(FileVersion.original_filename.ilike(pattern))
                    .order_by(FileVersion.created_at.desc())
                    .limit(per_kind)
                )
            ).scalars()
        )
        for item in files:
            results.append(
                search_result(
                    kind="file",
                    entity_id=item.id,
                    title=item.original_filename,
                    subtitle=f"v{item.version} · {item.content_type} · {item.sha256[:12]}",
                    section="files",
                    created_at=item.created_at,
                    status="active" if item.is_active else "inactive",
                    rank=45,
                )
            )

        audit_clauses = [
            AuditLog.action.ilike(pattern),
            AuditLog.entity_type.ilike(pattern),
            AuditLog.entity_id.ilike(pattern),
        ]
        if numeric is not None:
            audit_clauses.append(AuditLog.actor_telegram_id == numeric)
        audit_rows = list(
            (
                await session.execute(
                    select(AuditLog)
                    .where(or_(*audit_clauses))
                    .order_by(AuditLog.created_at.desc())
                    .limit(per_kind)
                )
            ).scalars()
        )
        for item in audit_rows:
            results.append(
                search_result(
                    kind="audit",
                    entity_id=item.id,
                    title=item.action,
                    subtitle=f"{item.entity_type or 'system'} · {item.entity_id or '—'}",
                    section="audit",
                    created_at=item.created_at,
                    rank=35,
                )
            )

        if exact_uuid is not None:
            broadcasts = list(
                (
                    await session.execute(
                        select(Broadcast).where(Broadcast.id == exact_uuid).limit(1)
                    )
                ).scalars()
            )
            for item in broadcasts:
                results.append(
                    search_result(
                        kind="broadcast",
                        entity_id=item.id,
                        title="Broadcast",
                        subtitle=item.text,
                        section="broadcasts",
                        created_at=item.created_at,
                        status=item.status,
                        rank=120,
                    )
                )

    results.sort(
        key=lambda item: (
            item["rank"],
            item["created_at"] or "",
            item["title"].casefold(),
        ),
        reverse=True,
    )
    return {"query": query, "items": results[:limit], "total": len(results)}
