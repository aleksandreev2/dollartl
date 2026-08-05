from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import delete, func, or_, select, update

from dollartl.admin.auth import AdminPrincipal, require_admin
from dollartl.admin.catalog_ops_common import (
    PublicationUpdate,
    RollbackRequest,
    TitleUpdate,
    audit,
    ensure_not_conflicted,
    iso,
    normalized_aliases,
    save_release_revision,
    save_title_revision,
    title_snapshot,
)
from dollartl.config import get_settings
from dollartl.db.catalog_revision_models import TitleRevision
from dollartl.db.models import DeepLink, Release, Title, TitleAlias
from dollartl.db.session import SessionFactory
from dollartl.services.catalog import CatalogService
from dollartl.storage import S3Storage

Admin = Annotated[AdminPrincipal, Depends(require_admin)]
router = APIRouter()


def title_row(title: Title, aliases: list[str], release_count: int) -> dict[str, Any]:
    return {
        "id": str(title.id),
        "slug": title.slug,
        "english_title": title.english_title,
        "original_title": title.original_title,
        "original_language": title.original_language,
        "description": title.description,
        "publication_status": title.publication_status,
        "cover_object_key": title.cover_object_key,
        "boosty_url": title.boosty_url,
        "is_published": title.is_published,
        "published_at": iso(title.published_at),
        "latest_chapter": title.latest_chapter,
        "created_at": iso(title.created_at),
        "updated_at": iso(title.updated_at),
        "aliases": aliases,
        "release_count": release_count,
    }


async def aliases_for(session, title_id: UUID) -> list[str]:
    return list(
        (
            await session.execute(
                select(TitleAlias.alias)
                .where(TitleAlias.title_id == title_id)
                .order_by(TitleAlias.alias.asc())
            )
        ).scalars()
    )


@router.get("/titles")
async def list_titles(
    admin: Admin,
    q: str = Query(default="", max_length=255),
    status: str = Query(default="all", max_length=30),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=10, le=100),
) -> dict[str, Any]:
    del admin
    filters = []
    if q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                Title.english_title.ilike(pattern),
                Title.original_title.ilike(pattern),
                Title.slug.ilike(pattern),
                Title.id.in_(select(TitleAlias.title_id).where(TitleAlias.alias.ilike(pattern))),
            )
        )
    if status == "published":
        filters.append(Title.is_published.is_(True))
    elif status == "draft":
        filters.append(Title.is_published.is_(False))
    elif status in {"ongoing", "completed", "hiatus"}:
        filters.append(Title.publication_status == status)
    async with SessionFactory() as session:
        total = int((await session.execute(select(func.count(Title.id)).where(*filters))).scalar_one())
        rows = list(
            (
                await session.execute(
                    select(Title)
                    .where(*filters)
                    .order_by(Title.updated_at.desc(), Title.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )
        items = []
        for item in rows:
            aliases = await aliases_for(session, item.id)
            count = int(
                (await session.execute(select(func.count(Release.id)).where(Release.title_id == item.id))).scalar_one()
            )
            items.append(title_row(item, aliases, count))
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": max(1, (total + page_size - 1) // page_size),
        "items": items,
    }


@router.get("/titles/{title_id}")
async def title_detail(title_id: UUID, admin: Admin) -> dict[str, Any]:
    del admin
    async with SessionFactory() as session:
        title = await session.get(Title, title_id)
        if title is None:
            raise HTTPException(status_code=404, detail="Тайтл не найден")
        aliases = await aliases_for(session, title.id)
        releases = list(
            (
                await session.execute(
                    select(Release)
                    .where(Release.title_id == title.id)
                    .order_by(Release.chapter_start, Release.chapter_end)
                )
            ).scalars()
        )
        revisions = list(
            (
                await session.execute(
                    select(TitleRevision)
                    .where(TitleRevision.title_id == title.id)
                    .order_by(TitleRevision.revision.desc())
                    .limit(50)
                )
            ).scalars()
        )
        cover_url = None
        if title.cover_object_key:
            cover_url = await asyncio.to_thread(
                S3Storage(get_settings()).presigned_get_url,
                title.cover_object_key,
                expires_seconds=900,
            )
        return {
            "title": title_row(title, aliases, len(releases)),
            "cover_url": cover_url,
            "releases": [
                {
                    "id": str(item.id),
                    "chapter_start": item.chapter_start,
                    "chapter_end": item.chapter_end,
                    "chapter_label": item.chapter_label,
                    "display_name": item.display_name,
                    "boosty_url": item.boosty_url,
                    "is_published": item.is_published,
                    "comments_enabled": item.comments_enabled,
                    "validation_status": item.validation_status,
                    "validation_message": item.validation_message,
                    "updated_at": iso(item.updated_at),
                }
                for item in releases
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


@router.put("/titles/{title_id}")
async def edit_title(title_id: UUID, payload: TitleUpdate, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        title = (
            await session.execute(select(Title).where(Title.id == title_id).with_for_update())
        ).scalar_one_or_none()
        if title is None:
            raise HTTPException(status_code=404, detail="Тайтл не найден")
        ensure_not_conflicted(title.updated_at, payload.expected_updated_at)
        duplicate = (
            await session.execute(select(Title.id).where(Title.slug == payload.slug, Title.id != title.id))
        ).scalar_one_or_none()
        if duplicate:
            raise HTTPException(status_code=409, detail="Этот slug уже используется")
        before = await title_snapshot(session, title)
        await save_title_revision(session, title=title, actor_id=admin.telegram_id, reason=payload.reason)
        title.slug = payload.slug
        title.english_title = payload.english_title.strip()
        title.original_title = payload.original_title.strip()
        title.original_language = payload.original_language.strip()
        title.description = payload.description.strip()
        title.publication_status = payload.publication_status
        title.boosty_url = payload.boosty_url or None
        await session.execute(delete(TitleAlias).where(TitleAlias.title_id == title.id))
        for normalized, alias in normalized_aliases(title.english_title, title.original_title, *payload.aliases):
            session.add(TitleAlias(title_id=title.id, alias=alias, normalized_alias=normalized))
        session.add(
            audit(
                actor_id=admin.telegram_id,
                action="catalog.title.updated",
                entity_type="title",
                entity_id=str(title.id),
                payload={"reason": payload.reason, "before": before},
            )
        )
        await session.commit()
        await session.refresh(title)
        return {"ok": True, "updated_at": iso(title.updated_at)}


@router.post("/titles/{title_id}/cover")
async def upload_cover(
    title_id: UUID,
    admin: Admin,
    file: UploadFile = File(...),
    expected_updated_at: datetime = Query(...),
    reason: str = Query(..., min_length=3, max_length=1000),
) -> dict[str, Any]:
    content_type = file.content_type or "application/octet-stream"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Обложка должна быть изображением")
    settings = get_settings()
    suffix = Path(file.filename or "cover.jpg").suffix or ".jpg"
    temp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    temp.close()
    path = Path(temp.name)
    size = 0
    key = f"titles/{title_id}/covers/{uuid4().hex}{suffix.lower()}"
    storage = S3Storage(settings)
    try:
        with path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.user_upload_max_bytes:
                    raise HTTPException(status_code=413, detail="Обложка превышает лимит")
                destination.write(chunk)
        with path.open("rb") as stream:
            stored = await asyncio.to_thread(storage.upload_fileobj, stream, key, content_type)
        try:
            async with SessionFactory() as session:
                title = (
                    await session.execute(select(Title).where(Title.id == title_id).with_for_update())
                ).scalar_one_or_none()
                if title is None:
                    raise HTTPException(status_code=404, detail="Тайтл не найден")
                ensure_not_conflicted(title.updated_at, expected_updated_at)
                await save_title_revision(session, title=title, actor_id=admin.telegram_id, reason=reason)
                previous_key = title.cover_object_key
                title.cover_object_key = stored.key
                title.cover_content_type = content_type
                session.add(
                    audit(
                        actor_id=admin.telegram_id,
                        action="catalog.title.cover_updated",
                        entity_type="title",
                        entity_id=str(title.id),
                        payload={"reason": reason, "previous_key": previous_key, "object_key": stored.key},
                    )
                )
                await session.commit()
                await session.refresh(title)
                return {"ok": True, "updated_at": iso(title.updated_at), "size_bytes": stored.size}
        except Exception:
            await asyncio.to_thread(storage.delete, key)
            raise
    finally:
        path.unlink(missing_ok=True)


@router.post("/titles/{title_id}/publication")
async def set_publication(title_id: UUID, payload: PublicationUpdate, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        title = (
            await session.execute(select(Title).where(Title.id == title_id).with_for_update())
        ).scalar_one_or_none()
        if title is None:
            raise HTTPException(status_code=404, detail="Тайтл не найден")
        ensure_not_conflicted(title.updated_at, payload.expected_updated_at)
        await save_title_revision(session, title=title, actor_id=admin.telegram_id, reason=payload.reason)
        if payload.published:
            link = await CatalogService(session).publish_title(title=title, admin_telegram_id=admin.telegram_id)
            return {"ok": True, "published": True, "deep_link_token": link.token}
        releases = list(
            (
                await session.execute(
                    select(Release)
                    .where(Release.title_id == title.id, Release.is_published.is_(True))
                    .with_for_update()
                )
            ).scalars()
        )
        for release in releases:
            await save_release_revision(
                session,
                release=release,
                actor_id=admin.telegram_id,
                reason=f"Cascade unpublish: {payload.reason}",
            )
            release.is_published = False
        title.is_published = False
        title.latest_chapter = 0
        await session.execute(update(DeepLink).where(DeepLink.title_id == title.id).values(is_active=False))
        if releases:
            await session.execute(
                update(DeepLink)
                .where(DeepLink.release_id.in_([item.id for item in releases]))
                .values(is_active=False)
            )
        session.add(
            audit(
                actor_id=admin.telegram_id,
                action="catalog.title.unpublished",
                entity_type="title",
                entity_id=str(title.id),
                payload={"reason": payload.reason, "cascade_releases": len(releases)},
            )
        )
        await session.commit()
        await session.refresh(title)
        return {"ok": True, "published": False, "updated_at": iso(title.updated_at)}


@router.post("/titles/{title_id}/rollback/{revision_id}")
async def rollback_title(
    title_id: UUID, revision_id: UUID, payload: RollbackRequest, admin: Admin
) -> dict[str, Any]:
    async with SessionFactory() as session:
        title = (
            await session.execute(select(Title).where(Title.id == title_id).with_for_update())
        ).scalar_one_or_none()
        revision = await session.get(TitleRevision, revision_id)
        if title is None or revision is None or revision.title_id != title_id:
            raise HTTPException(status_code=404, detail="Версия тайтла не найдена")
        ensure_not_conflicted(title.updated_at, payload.expected_updated_at)
        snapshot = dict(revision.snapshot or {})
        slug = str(snapshot.get("slug") or title.slug)
        duplicate = (
            await session.execute(select(Title.id).where(Title.slug == slug, Title.id != title.id))
        ).scalar_one_or_none()
        if duplicate:
            raise HTTPException(status_code=409, detail="Slug из версии уже занят")
        await save_title_revision(
            session,
            title=title,
            actor_id=admin.telegram_id,
            reason=f"Before rollback to revision {revision.revision}: {payload.reason}",
        )
        for field in (
            "slug",
            "english_title",
            "original_title",
            "original_language",
            "description",
            "publication_status",
            "cover_object_key",
            "cover_content_type",
            "boosty_url",
        ):
            if field in snapshot:
                setattr(title, field, snapshot[field])
        await session.execute(delete(TitleAlias).where(TitleAlias.title_id == title.id))
        for normalized, alias in normalized_aliases(*[str(value) for value in snapshot.get("aliases", [])]):
            session.add(TitleAlias(title_id=title.id, alias=alias, normalized_alias=normalized))
        session.add(
            audit(
                actor_id=admin.telegram_id,
                action="catalog.title.rolled_back",
                entity_type="title",
                entity_id=str(title.id),
                payload={"revision": revision.revision, "reason": payload.reason},
            )
        )
        await session.commit()
        await session.refresh(title)
        return {"ok": True, "updated_at": iso(title.updated_at)}


@router.get("/titles/{title_id}/preview")
async def preview_title(title_id: UUID, admin: Admin) -> dict[str, Any]:
    del admin
    async with SessionFactory() as session:
        title = await session.get(Title, title_id)
        if title is None:
            raise HTTPException(status_code=404, detail="Тайтл не найден")
        releases = list(
            (
                await session.execute(
                    select(Release)
                    .where(Release.title_id == title.id)
                    .order_by(Release.chapter_end.desc())
                    .limit(5)
                )
            ).scalars()
        )
        warnings = []
        if not title.cover_object_key:
            warnings.append("Обложка не загружена")
        if not title.description.strip():
            warnings.append("Описание пустое")
        bot_html = (
            f"📚 <b>{title.english_title}</b>\n"
            f"<i>{title.original_title}</i>\n\n"
            f"{title.description or 'Описание пока не добавлено.'}\n\n"
            f"Статус: <b>{title.publication_status}</b> · главы до {title.latest_chapter}"
        )
        suffix = (
            "\n\nПоследние пакеты:\n" + "\n".join(f"• {item.chapter_label}" for item in releases)
            if releases
            else "\n\nПакеты пока не добавлены."
        )
        return {"bot_html": bot_html, "channel_html": bot_html + suffix, "warnings": warnings}
