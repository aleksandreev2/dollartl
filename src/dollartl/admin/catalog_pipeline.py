from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import or_, select

from dollartl.admin.auth import AdminPrincipal, require_admin
from dollartl.config import get_settings
from dollartl.db.models import Title, TitleAlias
from dollartl.db.session import SessionFactory
from dollartl.files.catalog_metadata import analyse_catalog_file, merge_catalog_analysis
from dollartl.services.catalog_types import normalize_title

Admin = Annotated[AdminPrincipal, Depends(require_admin)]
router = APIRouter()


async def _save_upload(upload: UploadFile, kind: str) -> Path:
    settings = get_settings()
    suffix = ".pdf" if kind == "pdf" else ".epub"
    temporary = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    temporary.close()
    path = Path(temporary.name)
    size = 0
    try:
        with path.open("wb") as destination:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > settings.admin_upload_max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"{kind.upper()} превышает административный лимит",
                    )
                destination.write(chunk)
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


async def _possible_duplicates(title: str) -> list[dict[str, Any]]:
    normalized = normalize_title(title)
    if not normalized:
        return []
    pattern = f"%{title.strip()}%"
    normalized_pattern = f"%{normalized}%"
    async with SessionFactory() as session:
        rows = list(
            (
                await session.execute(
                    select(Title)
                    .outerjoin(TitleAlias, TitleAlias.title_id == Title.id)
                    .where(
                        or_(
                            Title.english_title.ilike(pattern),
                            Title.original_title.ilike(pattern),
                            TitleAlias.normalized_alias.like(normalized_pattern),
                        )
                    )
                    .distinct()
                    .order_by(Title.updated_at.desc())
                    .limit(5)
                )
            ).scalars()
        )
    return [
        {
            "id": str(item.id),
            "english_title": item.english_title,
            "original_title": item.original_title,
            "slug": item.slug,
            "is_published": item.is_published,
        }
        for item in rows
    ]


@router.post("/pipeline/analyze")
async def analyse_pipeline(
    admin: Admin,
    pdf: UploadFile | None = File(default=None),
    epub: UploadFile | None = File(default=None),
    source_url: str | None = Form(default=None, max_length=2000),
) -> dict[str, Any]:
    del admin
    if pdf is None and epub is None:
        raise HTTPException(status_code=400, detail="Загрузите PDF, EPUB или оба файла")

    temporary: list[Path] = []
    analysed = []
    try:
        for kind, upload in (("pdf", pdf), ("epub", epub)):
            if upload is None:
                continue
            filename = Path(upload.filename or f"release.{kind}").name
            try:
                path = await _save_upload(upload, kind)
                temporary.append(path)
                result = await asyncio.to_thread(analyse_catalog_file, path, kind, filename)
            except (ValueError, OSError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Не удалось проанализировать {kind.upper()}: {exc}",
                ) from exc
            analysed.append(result)

        payload = merge_catalog_analysis(analysed, source_url=source_url)
        suggested = payload.get("suggested") or {}
        payload["possible_duplicates"] = await _possible_duplicates(
            str(suggested.get("english_title") or "")
        )
        return payload
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)
