from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import exists, select, text

from dollartl.admin.auth import AdminPrincipal, require_admin
from dollartl.admin.catalog_ops_common import (
    CleanupRequest,
    RetryPublicationsRequest,
    audit,
    iso,
)
from dollartl.config import get_settings
from dollartl.db.models import (
    AuditLog,
    ChannelPublication,
    DownloadEvent,
    FileVersion,
    OutboxEvent,
    ReleaseFile,
)
from dollartl.db.session import SessionFactory
from dollartl.storage import S3Storage

Admin = Annotated[AdminPrincipal, Depends(require_admin)]
router = APIRouter()


async def _previous_result(session, *, action: str, key: str) -> dict[str, Any] | None:
    item = (
        await session.execute(
            select(AuditLog)
            .where(AuditLog.action == action, AuditLog.correlation_id == key)
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return dict(item.payload or {}) if item else None


async def _cleanup_candidates(session, *, min_age_days: int) -> list[FileVersion]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=min_age_days)
    return list(
        (
            await session.execute(
                select(FileVersion)
                .join(ReleaseFile, ReleaseFile.id == FileVersion.release_file_id)
                .where(
                    FileVersion.is_active.is_(False),
                    FileVersion.version != ReleaseFile.current_version,
                    FileVersion.created_at <= cutoff,
                    ~exists(
                        select(DownloadEvent.id).where(
                            DownloadEvent.file_version_id == FileVersion.id
                        )
                    ),
                )
                .order_by(FileVersion.created_at.asc(), FileVersion.id.asc())
                .limit(5000)
            )
        ).scalars()
    )


@router.post("/files/cleanup")
async def cleanup_inactive_files(payload: CleanupRequest, admin: Admin) -> dict[str, Any]:
    action = "catalog.file_cleanup.completed"
    async with SessionFactory() as session:
        previous = await _previous_result(
            session, action=action, key=payload.idempotency_key
        )
        if previous is not None:
            return {**previous, "replayed": True}
        candidates = await _cleanup_candidates(session, min_age_days=payload.min_age_days)
        preview = {
            "candidate_count": len(candidates),
            "bytes": sum(item.size_bytes for item in candidates),
            "confirmation": f"DELETE {len(candidates)} FILE VERSIONS",
            "items": [
                {
                    "id": str(item.id),
                    "filename": item.original_filename,
                    "version": item.version,
                    "size_bytes": item.size_bytes,
                    "created_at": iso(item.created_at),
                }
                for item in candidates[:100]
            ],
        }
        if payload.dry_run:
            return {**preview, "dry_run": True, "replayed": False}
        if payload.confirmation != preview["confirmation"]:
            raise HTTPException(
                status_code=409,
                detail=f"Подтверждение изменилось. Требуется: {preview['confirmation']}",
            )
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('dollartl.catalog.file_cleanup'))")
        )
        candidates = await _cleanup_candidates(session, min_age_days=payload.min_age_days)
        refreshed_confirmation = f"DELETE {len(candidates)} FILE VERSIONS"
        if payload.confirmation != refreshed_confirmation:
            raise HTTPException(
                status_code=409,
                detail=f"Список изменился. Новый dry-run требует: {refreshed_confirmation}",
            )
        storage = S3Storage(get_settings())
        deleted: list[str] = []
        failures: list[dict[str, str]] = []
        for item in candidates:
            try:
                await asyncio.to_thread(storage.delete, item.object_key)
            except Exception as exc:
                failures.append({"id": str(item.id), "error": f"{type(exc).__name__}: {exc}"})
                continue
            deleted.append(str(item.id))
            await session.delete(item)
        result = {
            "dry_run": False,
            "replayed": False,
            "deleted_count": len(deleted),
            "deleted_ids": deleted,
            "failed_count": len(failures),
            "failures": failures[:100],
            "bytes": sum(item.size_bytes for item in candidates if str(item.id) in deleted),
        }
        session.add(
            audit(
                actor_id=admin.telegram_id,
                action=action,
                entity_type="file_version_batch",
                entity_id=payload.idempotency_key,
                payload=result,
                correlation_id=payload.idempotency_key,
            )
        )
        await session.commit()
        return result


@router.get("/channel/failed-publications")
async def failed_publications(
    admin: Admin,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    del admin
    async with SessionFactory() as session:
        rows = list(
            (
                await session.execute(
                    select(ChannelPublication)
                    .where(ChannelPublication.status == "failed")
                    .order_by(ChannelPublication.updated_at.desc())
                    .limit(limit)
                )
            ).scalars()
        )
        return [
            {
                "id": str(item.id),
                "target_type": item.target_type,
                "target_id": item.target_id,
                "telegram_chat_id": item.telegram_chat_id,
                "error": item.error,
                "updated_at": iso(item.updated_at),
            }
            for item in rows
        ]


@router.post("/channel/retry-failed")
async def retry_failed_publications(
    payload: RetryPublicationsRequest, admin: Admin
) -> dict[str, Any]:
    action = "catalog.channel_publications.retry_batch.completed"
    unique_ids = list(dict.fromkeys(payload.publication_ids))
    async with SessionFactory() as session:
        previous = await _previous_result(
            session, action=action, key=payload.idempotency_key
        )
        if previous is not None:
            return {**previous, "replayed": True}
        rows = list(
            (
                await session.execute(
                    select(ChannelPublication).where(ChannelPublication.id.in_(unique_ids))
                )
            ).scalars()
        )
        found = {item.id: item for item in rows}
        eligible = [item for item in rows if item.status == "failed"]
        preview = {
            "requested": len(unique_ids),
            "eligible": len(eligible),
            "missing": [str(value) for value in unique_ids if value not in found],
            "not_failed": [str(item.id) for item in rows if item.status != "failed"],
        }
        if payload.dry_run:
            return {**preview, "dry_run": True, "replayed": False}
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('dollartl.catalog.retry_publications'))")
        )
        retried: list[str] = []
        missing_outbox: list[str] = []
        for item in eligible:
            event = (
                await session.execute(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.aggregate_type == item.target_type,
                        OutboxEvent.aggregate_id == item.target_id,
                    )
                    .order_by(OutboxEvent.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if event is None:
                missing_outbox.append(str(item.id))
                continue
            item.status = "pending"
            item.error = None
            event.published = False
            event.published_at = None
            retried.append(str(item.id))
            session.add(
                audit(
                    actor_id=admin.telegram_id,
                    action="catalog.channel_publication.retried",
                    entity_type="channel_publication",
                    entity_id=str(item.id),
                    payload={"target_type": item.target_type, "target_id": item.target_id},
                    correlation_id=payload.idempotency_key,
                )
            )
        result = {
            **preview,
            "dry_run": False,
            "replayed": False,
            "retried": len(retried),
            "retried_ids": retried,
            "missing_outbox": missing_outbox,
        }
        session.add(
            audit(
                actor_id=admin.telegram_id,
                action=action,
                entity_type="channel_publication_batch",
                entity_id=payload.idempotency_key,
                payload=result,
                correlation_id=payload.idempotency_key,
            )
        )
        await session.commit()
        return result
