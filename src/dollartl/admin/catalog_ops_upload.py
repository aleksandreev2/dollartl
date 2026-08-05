from __future__ import annotations

import asyncio
import hashlib
import tempfile
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select

from dollartl.admin.auth import AdminPrincipal, require_admin
from dollartl.admin.catalog_ops_common import audit, save_release_revision
from dollartl.config import get_settings
from dollartl.db.models import Release
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


@router.post("/releases/{release_id}/files/{file_kind}")
async def upload_release_file_transaction_safe(
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
    key = f"titles/releases/{release_id}/{file_kind}/{uuid4().hex}-{filename}"
    storage = S3Storage(settings)
    persisted = False
    try:
        size = 0
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
        try:
            async with SessionFactory() as session:
                release = (
                    await session.execute(
                        select(Release).where(Release.id == release_id).with_for_update()
                    )
                ).scalar_one_or_none()
                if release is None:
                    raise HTTPException(status_code=404, detail="Пакет не найден")
                await save_release_revision(
                    session, release=release, actor_id=admin.telegram_id, reason=reason
                )
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
                persisted = True
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
            if not persisted:
                await asyncio.to_thread(storage.delete, key)
            raise
    finally:
        path.unlink(missing_ok=True)
