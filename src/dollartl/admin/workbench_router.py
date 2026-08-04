from __future__ import annotations

import asyncio
import csv
import io
import json
import math
import re
from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from dollartl.admin.auth import AdminPrincipal, require_admin
from dollartl.config import get_settings
from dollartl.db.boosty_models import BoostyLink, BoostySyncError, BoostySyncRun
from dollartl.db.models import (
    AuditLog,
    ChannelPublication,
    FileVersion,
    OutboxEvent,
    Release,
    ReleaseFile,
    SystemSetting,
    Title,
    User,
    UserSettings,
)
from dollartl.db.session import SessionFactory
from dollartl.storage import S3Storage

Admin = Annotated[AdminPrincipal, Depends(require_admin)]
router = APIRouter(prefix="/admin/api", tags=["admin-workbench"])

_SETTING_KEY_RE = re.compile(r"^[a-z][a-z0-9_.-]{1,148}$")
_SECRET_FRAGMENTS = (
    "secret",
    "token",
    "password",
    "private_key",
    "access_key",
    "api_key",
    "encryption_key",
    "credential",
)


class ManualAccessUpdate(BaseModel):
    enabled: bool
    reason: str = Field(min_length=3, max_length=500)


class SettingUpdate(BaseModel):
    value: dict[str, Any]
    description: str | None = Field(default=None, max_length=2000)
    expected_updated_at: datetime | None = None


class SettingReset(BaseModel):
    expected_updated_at: datetime | None = None


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def page_meta(*, total: int, page: int, page_size: int) -> dict[str, int]:
    pages = max(1, math.ceil(total / page_size))
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": pages,
    }


def safe_setting_key(key: str) -> bool:
    lowered = key.lower()
    return bool(_SETTING_KEY_RE.fullmatch(key)) and not any(
        fragment in lowered for fragment in _SECRET_FRAGMENTS
    )


def setting_conflicts(item: SystemSetting, expected: datetime | None) -> bool:
    if expected is None or item.updated_at is None:
        return False
    left_value = (
        item.updated_at
        if item.updated_at.tzinfo
        else item.updated_at.replace(tzinfo=timezone.utc)
    )
    right_value = expected if expected.tzinfo else expected.replace(tzinfo=timezone.utc)
    left = left_value.astimezone(timezone.utc)
    right = right_value.astimezone(timezone.utc)
    return abs((left - right).total_seconds()) > 0.001


def _audit(
    *,
    admin_id: int,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any],
) -> AuditLog:
    return AuditLog(
        actor_telegram_id=admin_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
    )


@router.get("/boosty/workbench")
async def boosty_workbench(
    admin: Admin,
    q: str = Query(default="", max_length=120),
    status: str = Query(default="all", max_length=40),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=10, le=100),
) -> dict[str, Any]:
    del admin
    normalized = q.strip().lstrip("@")
    async with SessionFactory() as session:
        filters = []
        if status != "all":
            filters.append(BoostyLink.status == status)
        if normalized:
            pattern = f"%{normalized}%"
            query_clauses = [
                BoostyLink.boosty_username.ilike(pattern),
                BoostyLink.boosty_user_id.ilike(pattern),
                User.telegram_username.ilike(pattern),
            ]
            if normalized.isdigit():
                numeric = int(normalized)
                query_clauses.extend(
                    [User.telegram_id == numeric, User.anonymous_id == numeric]
                )
            filters.append(or_(*query_clauses))

        base = (
            select(BoostyLink, User, UserSettings)
            .join(User, User.id == BoostyLink.user_id)
            .outerjoin(UserSettings, UserSettings.user_id == User.id)
            .where(*filters)
        )
        total = int(
            (
                await session.execute(
                    select(func.count(BoostyLink.id))
                    .join(User, User.id == BoostyLink.user_id)
                    .where(*filters)
                )
            ).scalar_one()
        )
        rows = (
            await session.execute(
                base.order_by(BoostyLink.updated_at.desc(), BoostyLink.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()

        status_rows = (
            await session.execute(
                select(BoostyLink.status, func.count(BoostyLink.id)).group_by(
                    BoostyLink.status
                )
            )
        ).all()
        recent_syncs = list(
            (
                await session.execute(
                    select(BoostySyncRun)
                    .order_by(BoostySyncRun.started_at.desc())
                    .limit(8)
                )
            ).scalars()
        )
        recent_errors = list(
            (
                await session.execute(
                    select(BoostySyncError)
                    .order_by(BoostySyncError.created_at.desc())
                    .limit(12)
                )
            ).scalars()
        )

    return {
        **page_meta(total=total, page=page, page_size=page_size),
        "summary": {str(key): int(value) for key, value in status_rows},
        "items": [
            {
                "id": str(link.id),
                "user_id": str(user.id),
                "anonymous_id": user.anonymous_id,
                "display_name": (
                    preferences.display_name
                    if preferences and preferences.display_name
                    else user.anonymous_name
                ),
                "telegram_id": user.telegram_id,
                "telegram_username": user.telegram_username,
                "manual_download_access": user.manual_download_access,
                "boosty_user_id": link.boosty_user_id,
                "boosty_username": link.boosty_username,
                "tier_id": link.tier_id,
                "tier_name": link.tier_name,
                "status": link.status,
                "verified_at": iso(link.verified_at),
                "last_checked_at": iso(link.last_checked_at),
                "last_successful_check_at": iso(link.last_successful_check_at),
                "membership_expires_at": iso(link.membership_expires_at),
                "grace_ends_at": iso(link.grace_ends_at),
                "last_error_code": link.last_error_code,
                "last_error_message": link.last_error_message,
                "updated_at": iso(link.updated_at),
            }
            for link, user, preferences in rows
        ],
        "recent_syncs": [
            {
                "id": str(item.id),
                "run_type": item.run_type,
                "status": item.status,
                "started_at": iso(item.started_at),
                "finished_at": iso(item.finished_at),
                "scanned_count": item.scanned_count,
                "matched_count": item.matched_count,
                "changed_count": item.changed_count,
                "error_count": item.error_count,
            }
            for item in recent_syncs
        ],
        "recent_errors": [
            {
                "id": str(item.id),
                "user_id": str(item.user_id) if item.user_id else None,
                "error_code": item.error_code,
                "message": item.message,
                "created_at": iso(item.created_at),
            }
            for item in recent_errors
        ],
    }


@router.post("/boosty/users/{user_id}/manual-access")
async def update_manual_access(
    user_id: UUID,
    payload: ManualAccessUpdate,
    admin: Admin,
) -> dict[str, Any]:
    async with SessionFactory() as session:
        user = await session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        previous = user.manual_download_access
        user.manual_download_access = payload.enabled
        session.add(
            _audit(
                admin_id=admin.telegram_id,
                action="boosty.manual_access.updated",
                entity_type="user",
                entity_id=str(user.id),
                payload={
                    "previous": previous,
                    "enabled": payload.enabled,
                    "reason": payload.reason,
                },
            )
        )
        await session.commit()
        return {
            "ok": True,
            "user_id": str(user.id),
            "manual_download_access": user.manual_download_access,
        }


@router.get("/channel/publications")
async def channel_publications(
    admin: Admin,
    q: str = Query(default="", max_length=120),
    status: str = Query(default="all", max_length=30),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=10, le=100),
) -> dict[str, Any]:
    del admin
    filters = []
    if status != "all":
        filters.append(ChannelPublication.status == status)
    normalized = q.strip()
    if normalized:
        pattern = f"%{normalized}%"
        filters.append(
            or_(
                ChannelPublication.target_id.ilike(pattern),
                ChannelPublication.target_type.ilike(pattern),
                ChannelPublication.telegram_chat_id.ilike(pattern),
                ChannelPublication.error.ilike(pattern),
            )
        )
    async with SessionFactory() as session:
        total = int(
            (
                await session.execute(
                    select(func.count(ChannelPublication.id)).where(*filters)
                )
            ).scalar_one()
        )
        rows = list(
            (
                await session.execute(
                    select(ChannelPublication)
                    .where(*filters)
                    .order_by(
                        ChannelPublication.updated_at.desc(),
                        ChannelPublication.id.desc(),
                    )
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )
        status_rows = (
            await session.execute(
                select(
                    ChannelPublication.status,
                    func.count(ChannelPublication.id),
                ).group_by(ChannelPublication.status)
            )
        ).all()
        settings = get_settings()
    return {
        **page_meta(total=total, page=page, page_size=page_size),
        "summary": {str(key): int(value) for key, value in status_rows},
        "channel_username": settings.telegram_channel_username,
        "channel_posts_enabled": settings.channel_posts_enabled,
        "items": [
            {
                "id": str(item.id),
                "target_type": item.target_type,
                "target_id": item.target_id,
                "telegram_chat_id": item.telegram_chat_id,
                "telegram_message_id": item.telegram_message_id,
                "status": item.status,
                "error": item.error,
                "created_at": iso(item.created_at),
                "updated_at": iso(item.updated_at),
            }
            for item in rows
        ],
    }


@router.post("/channel/publications/{publication_id}/retry")
async def retry_channel_publication(
    publication_id: UUID,
    admin: Admin,
) -> dict[str, Any]:
    async with SessionFactory() as session:
        item = await session.get(ChannelPublication, publication_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Публикация не найдена")
        if item.status != "failed":
            raise HTTPException(
                status_code=409,
                detail="Повтор доступен только для публикации со статусом failed",
            )
        item.status = "pending"
        item.error = None
        event = (
            await session.execute(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_type == item.target_type,
                    OutboxEvent.aggregate_id == item.target_id,
                )
            )
        ).scalar_one_or_none()
        if event is not None:
            event.published = False
            event.published_at = None
        session.add(
            _audit(
                admin_id=admin.telegram_id,
                action="channel_publication.retry_requested",
                entity_type="channel_publication",
                entity_id=str(item.id),
                payload={
                    "target_type": item.target_type,
                    "target_id": item.target_id,
                    "outbox_requeued": event is not None,
                },
            )
        )
        await session.commit()
        return {"ok": True, "outbox_requeued": event is not None}


@router.get("/files/versions")
async def file_versions(
    admin: Admin,
    q: str = Query(default="", max_length=160),
    kind: Literal["all", "pdf", "epub"] = "all",
    cache: Literal["all", "cached", "uncached"] = "all",
    active: Literal["all", "active", "inactive"] = "active",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=10, le=100),
) -> dict[str, Any]:
    del admin
    filters = []
    if kind != "all":
        filters.append(ReleaseFile.file_kind == kind)
    if cache == "cached":
        filters.append(FileVersion.telegram_file_id.is_not(None))
    elif cache == "uncached":
        filters.append(FileVersion.telegram_file_id.is_(None))
    if active == "active":
        filters.append(FileVersion.is_active.is_(True))
    elif active == "inactive":
        filters.append(FileVersion.is_active.is_(False))
    normalized = q.strip()
    if normalized:
        pattern = f"%{normalized}%"
        filters.append(
            or_(
                FileVersion.original_filename.ilike(pattern),
                FileVersion.sha256.ilike(pattern),
                FileVersion.object_key.ilike(pattern),
                Title.english_title.ilike(pattern),
                Title.original_title.ilike(pattern),
                Release.display_name.ilike(pattern),
            )
        )

    joins = (
        select(FileVersion, ReleaseFile, Release, Title)
        .join(ReleaseFile, ReleaseFile.id == FileVersion.release_file_id)
        .join(Release, Release.id == ReleaseFile.release_id)
        .join(Title, Title.id == Release.title_id)
    )
    count_query = (
        select(func.count(FileVersion.id))
        .join(ReleaseFile, ReleaseFile.id == FileVersion.release_file_id)
        .join(Release, Release.id == ReleaseFile.release_id)
        .join(Title, Title.id == Release.title_id)
    )
    async with SessionFactory() as session:
        total = int((await session.execute(count_query.where(*filters))).scalar_one())
        rows = (
            await session.execute(
                joins.where(*filters)
                .order_by(FileVersion.created_at.desc(), FileVersion.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        summary = {
            "active": int(
                (
                    await session.execute(
                        select(func.count(FileVersion.id)).where(
                            FileVersion.is_active.is_(True)
                        )
                    )
                ).scalar_one()
            ),
            "cached": int(
                (
                    await session.execute(
                        select(func.count(FileVersion.id)).where(
                            FileVersion.telegram_file_id.is_not(None)
                        )
                    )
                ).scalar_one()
            ),
            "bytes": int(
                (
                    await session.execute(
                        select(func.coalesce(func.sum(FileVersion.size_bytes), 0)).where(
                            FileVersion.is_active.is_(True)
                        )
                    )
                ).scalar_one()
            ),
        }
    return {
        **page_meta(total=total, page=page, page_size=page_size),
        "summary": summary,
        "items": [
            {
                "id": str(version.id),
                "release_file_id": str(release_file.id),
                "release_id": str(release.id),
                "title_id": str(title.id),
                "title": title.english_title,
                "release_label": release.chapter_label,
                "file_kind": release_file.file_kind,
                "version": version.version,
                "filename": version.original_filename,
                "content_type": version.content_type,
                "size_bytes": version.size_bytes,
                "sha256": version.sha256,
                "telegram_cached": bool(version.telegram_file_id),
                "is_active": version.is_active,
                "created_at": iso(version.created_at),
            }
            for version, release_file, release, title in rows
        ],
    }


@router.post("/files/versions/{version_id}/verify")
async def verify_file_version(version_id: UUID, admin: Admin) -> dict[str, Any]:
    settings = get_settings()
    async with SessionFactory() as session:
        item = await session.get(FileVersion, version_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Версия файла не найдена")
        object_key = item.object_key
        expected_size = item.size_bytes
    head = await asyncio.to_thread(S3Storage(settings).head, object_key)
    actual_size = int(head.get("ContentLength", 0)) if head else None
    ok = head is not None and actual_size == expected_size
    async with SessionFactory() as session:
        session.add(
            _audit(
                admin_id=admin.telegram_id,
                action="file_version.integrity_checked",
                entity_type="file_version",
                entity_id=str(version_id),
                payload={
                    "ok": ok,
                    "expected_size": expected_size,
                    "actual_size": actual_size,
                    "object_exists": head is not None,
                    "etag": head.get("ETag") if head else None,
                },
            )
        )
        await session.commit()
    return {
        "ok": ok,
        "object_exists": head is not None,
        "expected_size": expected_size,
        "actual_size": actual_size,
        "etag": head.get("ETag") if head else None,
    }


@router.post("/files/versions/{version_id}/clear-cache")
async def clear_file_cache(version_id: UUID, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        item = await session.get(FileVersion, version_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Версия файла не найдена")
        was_cached = bool(item.telegram_file_id)
        item.telegram_file_id = None
        item.telegram_file_unique_id = None
        session.add(
            _audit(
                admin_id=admin.telegram_id,
                action="file_version.telegram_cache_cleared",
                entity_type="file_version",
                entity_id=str(item.id),
                payload={"was_cached": was_cached},
            )
        )
        await session.commit()
        return {"ok": True, "was_cached": was_cached}


def _audit_filters(
    *,
    q: str,
    action: str,
    entity_type: str,
    actor_telegram_id: int | None,
) -> list[Any]:
    filters: list[Any] = []
    if action:
        filters.append(AuditLog.action == action)
    if entity_type:
        filters.append(AuditLog.entity_type == entity_type)
    if actor_telegram_id is not None:
        filters.append(AuditLog.actor_telegram_id == actor_telegram_id)
    normalized = q.strip()
    if normalized:
        pattern = f"%{normalized}%"
        filters.append(
            or_(
                AuditLog.action.ilike(pattern),
                AuditLog.entity_type.ilike(pattern),
                AuditLog.entity_id.ilike(pattern),
                AuditLog.correlation_id.ilike(pattern),
            )
        )
    return filters


@router.get("/audit/events")
async def audit_events(
    admin: Admin,
    q: str = Query(default="", max_length=160),
    action: str = Query(default="", max_length=150),
    entity_type: str = Query(default="", max_length=100),
    actor_telegram_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=40, ge=10, le=100),
) -> dict[str, Any]:
    del admin
    filters = _audit_filters(
        q=q,
        action=action,
        entity_type=entity_type,
        actor_telegram_id=actor_telegram_id,
    )
    async with SessionFactory() as session:
        total = int(
            (
                await session.execute(
                    select(func.count(AuditLog.id)).where(*filters)
                )
            ).scalar_one()
        )
        rows = list(
            (
                await session.execute(
                    select(AuditLog)
                    .where(*filters)
                    .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )
        actions = list(
            (
                await session.execute(
                    select(AuditLog.action)
                    .distinct()
                    .order_by(AuditLog.action)
                    .limit(300)
                )
            ).scalars()
        )
        entity_types = list(
            (
                await session.execute(
                    select(AuditLog.entity_type)
                    .where(AuditLog.entity_type.is_not(None))
                    .distinct()
                    .order_by(AuditLog.entity_type)
                    .limit(200)
                )
            ).scalars()
        )
    return {
        **page_meta(total=total, page=page, page_size=page_size),
        "actions": actions,
        "entity_types": entity_types,
        "items": [
            {
                "id": str(item.id),
                "actor_telegram_id": item.actor_telegram_id,
                "action": item.action,
                "entity_type": item.entity_type,
                "entity_id": item.entity_id,
                "payload": item.payload,
                "correlation_id": item.correlation_id,
                "created_at": iso(item.created_at),
            }
            for item in rows
        ],
    }


@router.get("/audit/export")
async def export_audit(
    admin: Admin,
    q: str = Query(default="", max_length=160),
    action: str = Query(default="", max_length=150),
    entity_type: str = Query(default="", max_length=100),
    actor_telegram_id: int | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=10000),
) -> dict[str, str]:
    del admin
    filters = _audit_filters(
        q=q,
        action=action,
        entity_type=entity_type,
        actor_telegram_id=actor_telegram_id,
    )
    async with SessionFactory() as session:
        rows = list(
            (
                await session.execute(
                    select(AuditLog)
                    .where(*filters)
                    .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                    .limit(limit)
                )
            ).scalars()
        )
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(
        [
            "id",
            "created_at",
            "actor_telegram_id",
            "action",
            "entity_type",
            "entity_id",
            "correlation_id",
            "payload_json",
        ]
    )
    for item in rows:
        writer.writerow(
            [
                str(item.id),
                iso(item.created_at),
                item.actor_telegram_id,
                item.action,
                item.entity_type,
                item.entity_id,
                item.correlation_id,
                json.dumps(item.payload, ensure_ascii=False, sort_keys=True),
            ]
        )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return {
        "filename": f"dollartl-audit-{stamp}.csv",
        "content": stream.getvalue(),
    }


@router.get("/settings/workbench")
async def settings_workbench(admin: Admin) -> dict[str, Any]:
    del admin
    settings = get_settings()
    async with SessionFactory() as session:
        rows = list(
            (
                await session.execute(
                    select(SystemSetting).order_by(SystemSetting.key)
                )
            ).scalars()
        )
    immutable = [
        ("app_env", settings.app_env, "environment"),
        ("admin_web_origin", settings.admin_web_origin, "environment"),
        (
            "telegram_channel_username",
            settings.telegram_channel_username,
            "environment",
        ),
        ("channel_posts_enabled", settings.channel_posts_enabled, "environment"),
        ("boosty_enabled", settings.boosty_enabled, "environment"),
        ("boosty_tier_id", settings.boosty_tier_id, "environment"),
        ("maintenance_mode", settings.maintenance_mode, "environment"),
        ("backup_enabled", settings.backup_enabled, "environment"),
        (
            "backup_replication_enabled",
            settings.backup_replication_enabled,
            "environment",
        ),
        ("backup_interval_hours", settings.backup_interval_hours, "environment"),
        (
            "backup_retention_count",
            settings.backup_retention_count,
            "environment",
        ),
        ("backup_retention_days", settings.backup_retention_days, "environment"),
        ("s3_bucket", settings.s3_bucket, "environment"),
        ("s3_backup_bucket", settings.s3_backup_bucket, "environment"),
        ("s3_region", settings.s3_region, "environment"),
    ]
    return {
        "notice": (
            "DB overrides are audited configuration records. Values backed by Railway "
            "environment variables become active only after the environment is synchronized "
            "and the service is redeployed. Secrets are never editable here."
        ),
        "overrides": [
            {
                "id": str(item.id),
                "key": item.key,
                "value": item.value,
                "description": item.description,
                "updated_at": iso(item.updated_at),
            }
            for item in rows
        ],
        "environment": [
            {"key": key, "value": value, "source": source}
            for key, value, source in immutable
        ],
    }


@router.put("/settings/workbench/{key}")
async def update_workbench_setting(
    key: str,
    payload: SettingUpdate,
    admin: Admin,
) -> dict[str, Any]:
    if not safe_setting_key(key):
        raise HTTPException(
            status_code=400,
            detail="Недопустимый ключ или попытка сохранить секрет",
        )
    async with SessionFactory() as session:
        item = (
            await session.execute(
                select(SystemSetting).where(SystemSetting.key == key)
            )
        ).scalar_one_or_none()
        if item is not None and setting_conflicts(item, payload.expected_updated_at):
            raise HTTPException(
                status_code=409,
                detail="Настройка была изменена в другой сессии. Обновите страницу.",
            )
        previous = item.value if item else None
        if item is None:
            item = SystemSetting(
                key=key,
                value=payload.value,
                description=payload.description,
            )
            session.add(item)
            await session.flush()
        else:
            item.value = payload.value
            item.description = payload.description
        session.add(
            _audit(
                admin_id=admin.telegram_id,
                action="system_setting.workbench_updated",
                entity_type="system_setting",
                entity_id=key,
                payload={"previous": previous, "value": payload.value},
            )
        )
        await session.commit()
        await session.refresh(item)
        return {
            "ok": True,
            "key": item.key,
            "value": item.value,
            "description": item.description,
            "updated_at": iso(item.updated_at),
            "restart_required": True,
        }


@router.post("/settings/workbench/{key}/reset")
async def reset_workbench_setting(
    key: str,
    payload: SettingReset,
    admin: Admin,
) -> dict[str, Any]:
    async with SessionFactory() as session:
        item = (
            await session.execute(
                select(SystemSetting).where(SystemSetting.key == key)
            )
        ).scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=404, detail="Override не найден")
        if setting_conflicts(item, payload.expected_updated_at):
            raise HTTPException(
                status_code=409,
                detail="Настройка была изменена в другой сессии. Обновите страницу.",
            )
        previous = item.value
        await session.delete(item)
        session.add(
            _audit(
                admin_id=admin.telegram_id,
                action="system_setting.workbench_reset",
                entity_type="system_setting",
                entity_id=key,
                payload={"previous": previous},
            )
        )
        await session.commit()
        return {"ok": True, "key": key, "restart_required": True}
