from __future__ import annotations

import asyncio
import hashlib
import tempfile
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select, update

from dollartl.admin.auth import AdminPrincipal, require_admin
from dollartl.admin.catalog_ops_common import (
    FileActivateRequest,
    PublicationUpdate,
    ReleaseUpdate,
    RollbackRequest,
    audit,
    ensure_not_conflicted,
    iso,
    release_snapshot,
    save_release_revision,
)
from dollartl.config import get_settings
from dollartl.db.catalog_revision_models import FileVersionInspection, ReleaseRevision
from dollartl.db.models import DeepLink, FileVersion, Release, ReleaseFile, Title
from dollartl.db.session import SessionFactory
from dollartl.files.chapter_detection import detect_chapter_range
from dollartl.services.catalog import CatalogService
from dollartl.storage import S3Storage

Admin = Annotated[AdminPrincipal, Depends(require_admin)]
router = APIRouter()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def release_row(item: Release) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "title_id": str(item.title_id),
        "chapter_start": item.chapter_start,
        "chapter_end": item.chapter_end,
        "chapter_label": item.chapter_label,
        "display_name": item.display_name,
        "boosty_url": item.boosty_url,
        "is_published": item.is_published,
        "published_at": iso(item.published_at),
        "comments_enabled": item.comments_enabled,
        "validation_status": item.validation_status,
        "validation_message": item.validation_message,
        "detection_report": item.detection_report or {},
        "created_at": iso(item.created_at),
        "updated_at": iso(item.updated_at),
    }


@router.get("/releases/{release_id}")
async def release_detail(release_id: UUID, admin: Admin) -> dict[str, Any]:
    del admin
    async with SessionFactory() as session:
        release = await session.get(Release, release_id)
        if release is None:
            raise HTTPException(status_code=404, detail="Пакет не найден")
        title = await session.get(Title, release.title_id)
        rows = (
            await session.execute(
                select(ReleaseFile, FileVersion, FileVersionInspection)
                .join(FileVersion, FileVersion.release_file_id == ReleaseFile.id)
                .outerjoin(FileVersionInspection, FileVersionInspection.file_version_id == FileVersion.id)
                .where(ReleaseFile.release_id == release.id)
                .order_by(ReleaseFile.file_kind, FileVersion.version.desc())
            )
        ).all()
        revisions = list(
            (
                await session.execute(
                    select(ReleaseRevision)
                    .where(ReleaseRevision.release_id == release.id)
                    .order_by(ReleaseRevision.revision.desc())
                    .limit(50)
                )
            ).scalars()
        )
        return {
            "release": release_row(release),
            "title": {
                "id": str(title.id),
                "english_title": title.english_title,
                "is_published": title.is_published,
            }
            if title
            else None,
            "files": [
                {
                    "release_file_id": str(group.id),
                    "file_kind": group.file_kind,
                    "current_version": group.current_version,
                    "id": str(version.id),
                    "version": version.version,
                    "filename": version.original_filename,
                    "size_bytes": version.size_bytes,
                    "sha256": version.sha256,
                    "telegram_cached": bool(version.telegram_file_id),
                    "is_active": version.is_active,
                    "inspection": inspection.inspection if inspection else {},
                    "created_at": iso(version.created_at),
                }
                for group, version, inspection in rows
            ],
            "revisions": [
                {
                    "id": str(item.id),
                    "revision": item.revision,
                    "reason": item.reason,
                    "actor_telegram_id": item.actor_telegram_id,
                    "created_at": iso(item.created_at),
                    "snapshot": item.snapshot,
                }
                for item in revisions
            ],
        }


@router.put("/releases/{release_id}")
async def edit_release(release_id: UUID, payload: ReleaseUpdate, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        release = (
            await session.execute(select(Release).where(Release.id == release_id).with_for_update())
        ).scalar_one_or_none()
        if release is None:
            raise HTTPException(status_code=404, detail="Пакет не найден")
        ensure_not_conflicted(release.updated_at, payload.expected_updated_at)
        overlap = (
            await session.execute(
                select(Release.id)
                .where(
                    Release.title_id == release.title_id,
                    Release.id != release.id,
                    Release.chapter_start <= payload.chapter_end,
                    Release.chapter_end >= payload.chapter_start,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if overlap:
            raise HTTPException(status_code=409, detail="Диапазон пересекается с другим пакетом")
        before = release_snapshot(release)
        await save_release_revision(session, release=release, actor_id=admin.telegram_id, reason=payload.reason)
        release.chapter_start = payload.chapter_start
        release.chapter_end = payload.chapter_end
        release.display_name = payload.display_name or None
        release.boosty_url = payload.boosty_url or None
        release.comments_enabled = payload.comments_enabled
        await CatalogService(session)._refresh_release_validation(release)
        session.add(
            audit(
                actor_id=admin.telegram_id,
                action="catalog.release.updated",
                entity_type="release",
                entity_id=str(release.id),
                payload={"reason": payload.reason, "before": before},
            )
        )
        await session.commit()
        await session.refresh(release)
        return {"ok": True, "updated_at": iso(release.updated_at), "validation_status": release.validation_status}


@router.post("/releases/{release_id}/publication")
async def set_publication(release_id: UUID, payload: PublicationUpdate, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        release = (
            await session.execute(select(Release).where(Release.id == release_id).with_for_update())
        ).scalar_one_or_none()
        if release is None:
            raise HTTPException(status_code=404, detail="Пакет не найден")
        ensure_not_conflicted(release.updated_at, payload.expected_updated_at)
        await save_release_revision(session, release=release, actor_id=admin.telegram_id, reason=payload.reason)
        if payload.published:
            try:
                link = await CatalogService(session).publish_release(release=release, admin_telegram_id=admin.telegram_id)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return {"ok": True, "published": True, "deep_link_token": link.token}
        release.is_published = False
        await session.execute(update(DeepLink).where(DeepLink.release_id == release.id).values(is_active=False))
        latest = int(
            (
                await session.execute(
                    select(func.coalesce(func.max(Release.chapter_end), 0)).where(
                        Release.title_id == release.title_id,
                        Release.id != release.id,
                        Release.is_published.is_(True),
                    )
                )
            ).scalar_one()
        )
        title = await session.get(Title, release.title_id)
        if title:
            title.latest_chapter = latest
        session.add(
            audit(
                actor_id=admin.telegram_id,
                action="catalog.release.unpublished",
                entity_type="release",
                entity_id=str(release.id),
                payload={"reason": payload.reason},
            )
        )
        await session.commit()
        await session.refresh(release)
        return {"ok": True, "published": False, "updated_at": iso(release.updated_at)}


@router.post("/releases/{release_id}/rollback/{revision_id}")
async def rollback_release(
    release_id: UUID, revision_id: UUID, payload: RollbackRequest, admin: Admin
) -> dict[str, Any]:
    async with SessionFactory() as session:
        release = (
            await session.execute(select(Release).where(Release.id == release_id).with_for_update())
        ).scalar_one_or_none()
        revision = await session.get(ReleaseRevision, revision_id)
        if release is None or revision is None or revision.release_id != release_id:
            raise HTTPException(status_code=404, detail="Версия пакета не найдена")
        ensure_not_conflicted(release.updated_at, payload.expected_updated_at)
        snapshot = dict(revision.snapshot or {})
        start = int(snapshot.get("chapter_start", release.chapter_start))
        end = int(snapshot.get("chapter_end", release.chapter_end))
        overlap = (
            await session.execute(
                select(Release.id)
                .where(
                    Release.title_id == release.title_id,
                    Release.id != release.id,
                    Release.chapter_start <= end,
                    Release.chapter_end >= start,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if overlap:
            raise HTTPException(status_code=409, detail="Диапазон из версии пересекается с другим пакетом")
        await save_release_revision(
            session,
            release=release,
            actor_id=admin.telegram_id,
            reason=f"Before rollback to revision {revision.revision}: {payload.reason}",
        )
        for field in (
            "chapter_start",
            "chapter_end",
            "display_name",
            "boosty_url",
            "comments_enabled",
            "validation_status",
            "validation_message",
            "detection_report",
        ):
            if field in snapshot:
                setattr(release, field, snapshot[field])
        session.add(
            audit(
                actor_id=admin.telegram_id,
                action="catalog.release.rolled_back",
                entity_type="release",
                entity_id=str(release.id),
                payload={"revision": revision.revision, "reason": payload.reason},
            )
        )
        await session.commit()
        await session.refresh(release)
        return {"ok": True, "updated_at": iso(release.updated_at)}


@router.post("/file-versions/{version_id}/activate")
async def activate_version(version_id: UUID, payload: FileActivateRequest, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        version = (
            await session.execute(select(FileVersion).where(FileVersion.id == version_id).with_for_update())
        ).scalar_one_or_none()
        if version is None:
            raise HTTPException(status_code=404, detail="Версия файла не найдена")
        group = await session.get(ReleaseFile, version.release_file_id)
        if group is None:
            raise HTTPException(status_code=409, detail="Группа файла отсутствует")
        release = (
            await session.execute(select(Release).where(Release.id == group.release_id).with_for_update())
        ).scalar_one_or_none()
        if release is None:
            raise HTTPException(status_code=409, detail="Пакет отсутствует")
        if version.is_active:
            return {"ok": True, "already_active": True}
        await save_release_revision(
            session,
            release=release,
            actor_id=admin.telegram_id,
            reason=f"Before file rollback: {payload.reason}",
        )
        await session.execute(
            update(FileVersion).where(FileVersion.release_file_id == group.id).values(is_active=False)
        )
        version.is_active = True
        group.current_version = version.version
        inspection = (
            await session.execute(
                select(FileVersionInspection).where(FileVersionInspection.file_version_id == version.id)
            )
        ).scalar_one_or_none()
        report = dict(release.detection_report or {})
        report[group.file_kind] = dict(inspection.inspection or {}) if inspection else {}
        release.detection_report = report
        await CatalogService(session)._refresh_release_validation(release)
        session.add(
            audit(
                actor_id=admin.telegram_id,
                action="catalog.file_version.activated",
                entity_type="file_version",
                entity_id=str(version.id),
                payload={
                    "release_id": str(release.id),
                    "file_kind": group.file_kind,
                    "version": version.version,
                    "reason": payload.reason,
                },
            )
        )
        await session.commit()
        return {"ok": True, "version": version.version, "validation_status": release.validation_status}


@router.post("/releases/{release_id}/files/{file_kind}")
async def upload_file(
    release_id: UUID,
    file_kind: str,
    admin: Admin,
    file: UploadFile = File(...),
    reason: str = Query(default="Upload new file version", min_length=3, max_length=1000),
) -> dict[str, Any]:
    if file_kind not in {"pdf", "epub"}:
        raise HTTPException(status_code=400, detail="Формат должен быть pdf или epub")
    settings = get_settings()
    filename = Path(file.filename or f"release.{file_kind}").name
    temp = tempfile.NamedTemporaryFile(suffix=f".{file_kind}", delete=False)
    temp.close()
    path = Path(temp.name)
    size = 0
    key = f"titles/releases/{release_id}/{file_kind}/{uuid4().hex}-{filename}"
    storage = S3Storage(settings)
    uploaded = False
    try:
        with path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.admin_upload_max_bytes:
                    raise HTTPException(status_code=413, detail="Файл превышает административный лимит")
                destination.write(chunk)
        detection = await asyncio.to_thread(detect_chapter_range, path, file_kind, filename)
        digest = await asyncio.to_thread(sha256, path)
        content_type = "application/pdf" if file_kind == "pdf" else "application/epub+zip"
        with path.open("rb") as stream:
            stored = await asyncio.to_thread(storage.upload_fileobj, stream, key, content_type)
        uploaded = True
        try:
            async with SessionFactory() as session:
                release = (
                    await session.execute(select(Release).where(Release.id == release_id).with_for_update())
                ).scalar_one_or_none()
                if release is None:
                    raise HTTPException(status_code=404, detail="Пакет не найден")
                await save_release_revision(session, release=release, actor_id=admin.telegram_id, reason=reason)
                version = await CatalogService(session).attach_release_file(
                    release=release,
                    file_kind=file_kind,
                    object_key=stored.key,
                    original_filename=filename,
                    content_type=content_type,
                    size_bytes=stored.size,
                    sha256=digest,
                    telegram_file_id=None,
                    telegram_file_unique_id=None,
                    detection=detection.as_dict(),
                    admin_telegram_id=admin.telegram_id,
                )
                session.add(
                    audit(
                        actor_id=admin.telegram_id,
                        action="catalog.release.file_uploaded",
                        entity_type="file_version",
                        entity_id=str(version.id),
                        payload={
                            "release_id": str(release_id),
                            "file_kind": file_kind,
                            "version": version.version,
                            "reason": reason,
                        },
                    )
                )
                await session.commit()
                return {
                    "ok": True,
                    "version_id": str(version.id),
                    "version": version.version,
                    "detection": detection.as_dict(),
                }
        except Exception:
            if uploaded:
                await asyncio.to_thread(storage.delete, key)
            raise
    finally:
        path.unlink(missing_ok=True)


@router.get("/releases/{release_id}/preview")
async def preview_release(release_id: UUID, admin: Admin) -> dict[str, Any]:
    del admin
    async with SessionFactory() as session:
        release = await session.get(Release, release_id)
        if release is None:
            raise HTTPException(status_code=404, detail="Пакет не найден")
        title = await session.get(Title, release.title_id)
        files = list(
            (
                await session.execute(
                    select(ReleaseFile.file_kind, FileVersion)
                    .join(FileVersion, FileVersion.release_file_id == ReleaseFile.id)
                    .where(ReleaseFile.release_id == release.id, FileVersion.is_active.is_(True))
                )
            ).all()
        )
        kinds = {kind for kind, _ in files}
        warnings = []
        if kinds != {"pdf", "epub"}:
            warnings.append("Нужны активные PDF и EPUB")
        if release.validation_status not in {"valid", "overridden"}:
            warnings.append(release.validation_message or "Проверка файлов не завершена")
        title_name = title.english_title if title else "Неизвестный тайтл"
        bot_html = (
            f"🆕 <b>{title_name}</b>\n"
            f"{release.chapter_label}\n\n"
            f"PDF: {'готов' if 'pdf' in kinds else 'нет'} · EPUB: {'готов' if 'epub' in kinds else 'нет'}\n"
            f"Комментарии: {'включены' if release.comments_enabled else 'выключены'}"
        )
        channel_html = bot_html + (f"\n\nBoosty: {release.boosty_url}" if release.boosty_url else "")
        return {"bot_html": bot_html, "channel_html": channel_html, "warnings": warnings}
