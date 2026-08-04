from __future__ import annotations

import asyncio
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from dollartl.admin.auth import AdminPrincipal, require_admin
from dollartl.config import get_settings
from dollartl.db.resilience_models import BackupRun
from dollartl.db.session import SessionFactory
from dollartl.resilience.backups import request_backup
from dollartl.resilience.health import dependency_snapshot, service_snapshot
from dollartl.storage import S3Storage

Admin = Annotated[AdminPrincipal, Depends(require_admin)]
router = APIRouter(prefix="/admin/api", tags=["admin-resilience"])


def serialize_backup(item: BackupRun) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "status": item.status,
        "trigger_type": item.trigger_type,
        "requested_by_admin_id": item.requested_by_admin_id,
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "created_at": item.created_at.isoformat(),
        "plaintext_size_bytes": item.plaintext_size_bytes,
        "encrypted_size_bytes": item.encrypted_size_bytes,
        "plaintext_sha256": item.plaintext_sha256,
        "encrypted_sha256": item.encrypted_sha256,
        "database_archive_verified": item.database_archive_verified,
        "restore_verified": item.restore_verified,
        "storage_replication_verified": item.storage_replication_verified,
        "source_object_count": item.source_object_count,
        "replicated_object_count": item.replicated_object_count,
        "replicated_bytes": item.replicated_bytes,
        "telegram_delivery_status": item.telegram_delivery_status,
        "telegram_message_id": item.telegram_message_id,
        "verification_details": item.verification_details,
        "database_available": bool(item.database_object_key),
        "manifest_available": bool(item.manifest_object_key),
        "error": item.error,
    }


@router.get("/backups")
async def list_backups(
    admin: Admin,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    del admin
    async with SessionFactory() as session:
        items = list(
            (
                await session.execute(
                    select(BackupRun)
                    .order_by(BackupRun.created_at.desc())
                    .limit(limit)
                )
            ).scalars()
        )
        return [serialize_backup(item) for item in items]


@router.post("/backups/trigger", status_code=202)
async def trigger_backup(admin: Admin) -> dict[str, Any]:
    settings = get_settings()
    if not settings.backup_encryption_key.get_secret_value():
        raise HTTPException(
            status_code=409,
            detail="BACKUP_ENCRYPTION_KEY is not configured",
        )
    if not settings.s3_backup_bucket:
        raise HTTPException(status_code=409, detail="S3_BACKUP_BUCKET is not configured")
    item = await request_backup(admin_telegram_id=admin.telegram_id)
    return serialize_backup(item)


@router.get("/backups/{backup_id}/download")
async def backup_download(backup_id: UUID, admin: Admin) -> dict[str, Any]:
    del admin
    settings = get_settings()
    async with SessionFactory() as session:
        item = await session.get(BackupRun, backup_id)
        if item is None or not item.database_object_key:
            raise HTTPException(status_code=404, detail="Backup archive is unavailable")
        key = item.database_object_key
        filename = f"dollartl-{item.id}.dtlbak"
    url = await asyncio.to_thread(
        S3Storage.backup(settings).presigned_get_url,
        key,
        expires_seconds=settings.backup_download_url_seconds,
        filename=filename,
    )
    return {
        "url": url,
        "filename": filename,
        "expires_in": settings.backup_download_url_seconds,
    }


@router.get("/backups/{backup_id}/manifest")
async def backup_manifest(backup_id: UUID, admin: Admin) -> dict[str, Any]:
    del admin
    settings = get_settings()
    async with SessionFactory() as session:
        item = await session.get(BackupRun, backup_id)
        if item is None or not item.manifest_object_key:
            raise HTTPException(status_code=404, detail="Backup manifest is unavailable")
        key = item.manifest_object_key
    url = await asyncio.to_thread(
        S3Storage.backup(settings).presigned_get_url,
        key,
        expires_seconds=900,
        filename=f"dollartl-{backup_id}-manifest.json",
    )
    return {"url": url, "expires_in": 900}


@router.get("/resilience")
async def resilience_status(admin: Admin) -> dict[str, Any]:
    del admin
    settings = get_settings()
    dependencies, services = await asyncio.gather(
        dependency_snapshot(settings),
        service_snapshot(settings),
    )
    return {
        "backup_enabled": settings.backup_enabled,
        "backup_replication_enabled": settings.backup_replication_enabled,
        "backup_interval_hours": settings.backup_interval_hours,
        "backup_retention_count": settings.backup_retention_count,
        "backup_retention_days": settings.backup_retention_days,
        "dependencies": dependencies,
        **services,
    }
