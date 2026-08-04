from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from dollartl.admin.auth import AdminPrincipal, require_admin
from dollartl.config import get_settings
from dollartl.db.session import SessionFactory
from dollartl.db.suggestion_models import SuggestionFile, TitleSuggestion
from dollartl.storage import S3Storage

Admin = Annotated[AdminPrincipal, Depends(require_admin)]
router = APIRouter(prefix="/admin/api", tags=["admin-raw"])


@router.get("/suggestions/{suggestion_id}/raw-link")
async def raw_review_link(suggestion_id: UUID, admin: Admin) -> dict[str, str | int]:
    del admin
    async with SessionFactory() as session:
        suggestion = await session.get(TitleSuggestion, suggestion_id)
        if suggestion is None or suggestion.status == "draft":
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        raw = (
            await session.execute(
                select(SuggestionFile).where(
                    SuggestionFile.suggestion_id == suggestion.id,
                    SuggestionFile.file_kind == "raw",
                    SuggestionFile.validation_status == "valid",
                )
            )
        ).scalar_one_or_none()
        if raw is None:
            raise HTTPException(status_code=404, detail="Валидный raw-файл не найден")
        key = raw.object_key
        filename = raw.original_filename
        size = raw.size_bytes
        sha256 = raw.sha256
    url = await asyncio.to_thread(
        S3Storage(get_settings()).presigned_get_url,
        key,
        expires_seconds=300,
        filename=filename,
    )
    return {
        "url": url,
        "expires_in": 300,
        "filename": filename,
        "size_bytes": size,
        "sha256": sha256,
    }
