from __future__ import annotations

import asyncio
import hashlib
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select

from dollartl.admin.auth import AdminPrincipal, require_admin
from dollartl.admin.schemas import (
    BanCreate,
    BroadcastCreate,
    ChannelSettingsUpdate,
    CommentModeration,
    RatingWorkflow,
    ReleaseCreate,
    ReportUpdate,
    SuggestionDecision,
    SystemSettingUpdate,
    TitleCreate,
    ValidationOverride,
)
from dollartl.bot.dispatcher import create_bot
from dollartl.config import get_settings
from dollartl.db.admin_models import AdminUpload, Broadcast
from dollartl.db.boosty_models import BoostyLink, BoostySyncError, BoostySyncRun
from dollartl.db.community_models import (
    Comment,
    ModerationRule,
    Report,
    ReportMessage,
    TranslationRating,
    TranslationRatingStatusHistory,
)
from dollartl.db.models import (
    AuditLog,
    Ban,
    ChannelPublication,
    FileVersion,
    Release,
    SystemSetting,
    Title,
    User,
    UserSettings,
)
from dollartl.db.session import SessionFactory
from dollartl.db.suggestion_models import SuggestionFile, TitleSuggestion
from dollartl.files.chapter_detection import detect_chapter_range
from dollartl.services.access import AccessService
from dollartl.services.catalog import CatalogService
from dollartl.services.suggestions import SuggestionService
from dollartl.storage import S3Storage

Admin = Annotated[AdminPrincipal, Depends(require_admin)]
router = APIRouter(prefix="/admin/api", tags=["admin"])


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


async def _count(session, model, *conditions) -> int:
    return int((await session.execute(select(func.count(model.id)).where(*conditions))).scalar_one())


def _title(item: Title) -> dict[str, Any]:
    return {
        "id": str(item.id), "slug": item.slug, "english_title": item.english_title,
        "original_title": item.original_title, "original_language": item.original_language,
        "publication_status": item.publication_status, "description": item.description,
        "boosty_url": item.boosty_url, "is_published": item.is_published,
        "latest_chapter": item.latest_chapter, "published_at": _iso(item.published_at),
        "created_at": _iso(item.created_at),
    }


def _release(item: Release) -> dict[str, Any]:
    return {
        "id": str(item.id), "title_id": str(item.title_id),
        "chapter_start": item.chapter_start, "chapter_end": item.chapter_end,
        "display_name": item.display_name, "chapter_label": item.chapter_label,
        "boosty_url": item.boosty_url, "is_published": item.is_published,
        "published_at": _iso(item.published_at), "validation_status": item.validation_status,
        "validation_message": item.validation_message, "detection_report": item.detection_report,
    }


@router.get("/session")
async def session_info(admin: Admin) -> dict[str, Any]:
    return {"telegram_id": admin.telegram_id, "username": admin.username, "first_name": admin.first_name, "version": "0.7.0"}


@router.get("/overview")
async def overview(admin: Admin) -> dict[str, int]:
    del admin
    now = datetime.now(timezone.utc)
    async with SessionFactory() as session:
        return {
            "users": await _count(session, User),
            "active_vip": await _count(session, BoostyLink, BoostyLink.status == "active_vip"),
            "grace": await _count(session, BoostyLink, BoostyLink.status == "grace_period", BoostyLink.grace_ends_at > now),
            "published_titles": await _count(session, Title, Title.is_published.is_(True)),
            "releases": await _count(session, Release),
            "suggestions_pending": await _count(session, TitleSuggestion, TitleSuggestion.status == "under_review"),
            "comments": await _count(session, Comment, Comment.is_deleted.is_(False)),
            "ratings_new": await _count(session, TranslationRating, TranslationRating.status == "new"),
            "reports_open": await _count(session, Report, Report.status.in_(["open", "in_progress"])),
            "active_bans": await _count(session, Ban, Ban.is_active.is_(True)),
            "broadcasts_running": await _count(session, Broadcast, Broadcast.status.in_(["scheduled", "processing"])),
            "boosty_errors": await _count(session, BoostySyncError),
        }


@router.get("/titles")
async def list_titles(admin: Admin, query: str = Query(default="", max_length=255), limit: int = Query(default=200, ge=1, le=500)) -> list[dict[str, Any]]:
    del admin
    async with SessionFactory() as session:
        statement = select(Title)
        if query.strip():
            pattern = f"%{query.strip()}%"
            statement = statement.where(or_(Title.english_title.ilike(pattern), Title.original_title.ilike(pattern), Title.slug.ilike(pattern)))
        rows = list((await session.execute(statement.order_by(Title.created_at.desc()).limit(limit))).scalars())
        return [_title(item) for item in rows]


@router.post("/titles", status_code=201)
async def create_title(payload: TitleCreate, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        try:
            item = await CatalogService(session).create_title(
                english_title=payload.english_title, original_title=payload.original_title,
                original_language=payload.original_language, publication_status=payload.publication_status,
                boosty_url=payload.boosty_url, description=payload.description, aliases=payload.aliases,
                admin_telegram_id=admin.telegram_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _title(item)


@router.post("/titles/{title_id}/publish")
async def publish_title(title_id: UUID, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        service = CatalogService(session)
        item = await service.get_title(title_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Тайтл не найден")
        link = await service.publish_title(title=item, admin_telegram_id=admin.telegram_id)
        return {"ok": True, "deep_link_token": link.token, "title": _title(item)}


@router.get("/releases")
async def list_releases(admin: Admin, title_id: UUID | None = None, limit: int = Query(default=300, ge=1, le=500)) -> list[dict[str, Any]]:
    del admin
    async with SessionFactory() as session:
        statement = select(Release)
        if title_id:
            statement = statement.where(Release.title_id == title_id)
        rows = list((await session.execute(statement.order_by(Release.created_at.desc()).limit(limit))).scalars())
        return [_release(item) for item in rows]


@router.post("/releases", status_code=201)
async def create_release(payload: ReleaseCreate, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        service = CatalogService(session)
        title = await service.get_title(payload.title_id)
        if title is None:
            raise HTTPException(status_code=404, detail="Тайтл не найден")
        try:
            item = await service.create_release(
                title=title, chapter_start=payload.chapter_start, chapter_end=payload.chapter_end,
                boosty_url=payload.boosty_url, display_name=payload.display_name,
                admin_telegram_id=admin.telegram_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _release(item)


@router.post("/releases/{release_id}/files/{file_kind}")
async def upload_release_file(release_id: UUID, file_kind: str, admin: Admin, file: UploadFile = File(...)) -> dict[str, Any]:
    settings = get_settings()
    if file_kind not in {"pdf", "epub"}:
        raise HTTPException(status_code=400, detail="Формат должен быть pdf или epub")
    filename = Path(file.filename or f"release.{file_kind}").name
    temp = tempfile.NamedTemporaryFile(suffix=f".{file_kind}", delete=False)
    temp.close()
    path = Path(temp.name)
    size = 0
    try:
        with path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.admin_upload_max_bytes:
                    raise HTTPException(status_code=413, detail="Файл превышает административный лимит")
                destination.write(chunk)
        detection = await asyncio.to_thread(detect_chapter_range, path, file_kind, filename)
        digest = await asyncio.to_thread(_sha256, path)
        content_type = "application/pdf" if file_kind == "pdf" else "application/epub+zip"
        key = f"titles/releases/{release_id}/{file_kind}/{uuid4().hex}-{filename}"
        storage = S3Storage(settings)
        with path.open("rb") as stream:
            stored = await asyncio.to_thread(storage.upload_fileobj, stream, key, content_type)
        async with SessionFactory() as session:
            service = CatalogService(session)
            release = await service.get_release(release_id)
            if release is None:
                await asyncio.to_thread(storage.delete, key)
                raise HTTPException(status_code=404, detail="Пакет не найден")
            version = await service.attach_release_file(
                release=release, file_kind=file_kind, object_key=stored.key,
                original_filename=filename, content_type=content_type, size_bytes=stored.size,
                sha256=digest, telegram_file_id=None, telegram_file_unique_id=None,
                detection=detection.as_dict(), admin_telegram_id=admin.telegram_id,
            )
            return {"ok": True, "version": version.version, "detection": detection.as_dict(), "release": _release(release)}
    finally:
        path.unlink(missing_ok=True)


@router.post("/releases/{release_id}/override")
async def override_release(release_id: UUID, payload: ValidationOverride, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        service = CatalogService(session)
        item = await service.get_release(release_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Пакет не найден")
        await service.override_release_validation(release=item, admin_telegram_id=admin.telegram_id, reason=payload.reason)
        return {"ok": True, "release": _release(item)}


@router.post("/releases/{release_id}/publish")
async def publish_release(release_id: UUID, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        service = CatalogService(session)
        item = await service.get_release(release_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Пакет не найден")
        try:
            link = await service.publish_release(release=item, admin_telegram_id=admin.telegram_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "deep_link_token": link.token, "release": _release(item)}


@router.get("/users")
async def list_users(admin: Admin, query: str = Query(default="", max_length=100), limit: int = Query(default=200, ge=1, le=500)) -> list[dict[str, Any]]:
    del admin
    async with SessionFactory() as session:
        statement = select(User, UserSettings, BoostyLink).outerjoin(UserSettings, UserSettings.user_id == User.id).outerjoin(BoostyLink, BoostyLink.user_id == User.id)
        if query.strip():
            clauses = [User.telegram_username.ilike(f"%{query.strip().lstrip('@')}%")]
            if query.strip().isdigit():
                value = int(query.strip())
                clauses.extend([User.telegram_id == value, User.anonymous_id == value])
            statement = statement.where(or_(*clauses))
        rows = (await session.execute(statement.order_by(User.last_seen_at.desc()).limit(limit))).all()
        return [{
            "id": str(user.id), "telegram_id": user.telegram_id, "telegram_username": user.telegram_username,
            "anonymous_id": user.anonymous_id, "display_name": preferences.display_name if preferences else None,
            "is_active": user.is_active, "manual_download_access": user.manual_download_access,
            "last_seen_at": _iso(user.last_seen_at), "boosty_status": link.status if link else "unverified",
            "boosty_username": link.boosty_username if link else None,
            "grace_ends_at": _iso(link.grace_ends_at) if link else None,
        } for user, preferences, link in rows]


@router.post("/users/{user_id}/ban")
async def ban_user(user_id: UUID, payload: BanCreate, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        target = await session.get(User, user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        item = await AccessService(session).create_ban(
            target=target, ban_type=payload.ban_type, public_reason=payload.public_reason,
            admin_telegram_id=admin.telegram_id, expires_at=payload.expires_at,
            reason_template=payload.reason_template, internal_note=payload.internal_note,
        )
        return {"ok": True, "ban_id": str(item.id)}


@router.post("/users/{user_id}/unban")
async def unban_user(user_id: UUID, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        target = await session.get(User, user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        count = await AccessService(session).unban_user(target=target, admin_telegram_id=admin.telegram_id, note="Admin Mini App")
        return {"ok": True, "removed": count}


@router.get("/suggestions")
async def suggestions(admin: Admin, status: str = "under_review", limit: int = Query(default=200, ge=1, le=500)) -> list[dict[str, Any]]:
    del admin
    async with SessionFactory() as session:
        statement = select(TitleSuggestion, User).join(User, User.id == TitleSuggestion.user_id).where(TitleSuggestion.status != "draft")
        if status != "all":
            statement = statement.where(TitleSuggestion.status == status)
        rows = (await session.execute(statement.order_by(TitleSuggestion.submitted_at.desc()).limit(limit))).all()
        result = []
        for item, user in rows:
            raw = (await session.execute(select(SuggestionFile).where(SuggestionFile.suggestion_id == item.id, SuggestionFile.file_kind == "raw"))).scalar_one_or_none()
            result.append({
                "id": str(item.id), "original_title": item.original_title, "detected_language": item.detected_language,
                "chapter_count": item.chapter_count, "requested_chapter_end": item.requested_chapter_end,
                "publication_status": item.publication_status, "status": item.status, "vip_snapshot": item.vip_snapshot,
                "duplicate_review_required": item.duplicate_review_required, "public_reason": item.public_reason,
                "internal_note": item.internal_note, "linked_title_id": str(item.linked_title_id) if item.linked_title_id else None,
                "submitted_at": _iso(item.submitted_at),
                "raw_file": ({"filename": raw.original_filename, "size_bytes": raw.size_bytes, "validation_status": raw.validation_status} if raw else None),
                "user": {"id": str(user.id), "telegram_id": user.telegram_id, "anonymous_id": user.anonymous_id},
            })
        return result


@router.post("/suggestions/{suggestion_id}/decision")
async def decide_suggestion(suggestion_id: UUID, payload: SuggestionDecision, admin: Admin) -> dict[str, Any]:
    settings = get_settings()
    async with SessionFactory() as session:
        service = SuggestionService(session, settings)
        item = await service.get(suggestion_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        user = await session.get(User, item.user_id)
        try:
            await service.change_status(suggestion=item, new_status=payload.status, admin_telegram_id=admin.telegram_id, public_reason=payload.public_reason, internal_note=payload.internal_note, linked_title_id=payload.linked_title_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if user:
        bot = create_bot(settings)
        try:
            reason = f"\n\nReason:\n{payload.public_reason}" if payload.public_reason else ""
            await bot.send_message(user.telegram_id, f"💡 <b>SUGGESTION UPDATE</b>\n\nStatus: <b>{payload.status.replace('_', ' ').title()}</b>{reason}")
        finally:
            await bot.session.close()
    return {"ok": True}


@router.get("/comments")
async def comments(admin: Admin, limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, Any]]:
    del admin
    async with SessionFactory() as session:
        rows = (await session.execute(select(Comment, User).join(User, User.id == Comment.user_id).order_by(Comment.created_at.desc()).limit(limit))).all()
        return [{"id": str(item.id), "telegram_id": user.telegram_id, "anonymous_id": user.anonymous_id, "target_type": item.target_type, "original_body": item.original_body, "public_body": item.public_body, "replacement_count": item.replacement_count, "vip_snapshot": item.vip_snapshot, "is_deleted": item.is_deleted, "created_at": _iso(item.created_at)} for item, user in rows]


@router.post("/comments/{comment_id}/moderate")
async def moderate_comment(comment_id: UUID, payload: CommentModeration, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        item = await session.get(Comment, comment_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Комментарий не найден")
        item.is_deleted = payload.deleted
        item.deleted_at = datetime.now(timezone.utc) if payload.deleted else None
        item.deleted_by_admin_id = admin.telegram_id if payload.deleted else None
        session.add(AuditLog(actor_telegram_id=admin.telegram_id, action="comment.moderated", entity_type="comment", entity_id=str(item.id), payload={"deleted": payload.deleted}))
        await session.commit()
        return {"ok": True}


@router.get("/ratings")
async def ratings(admin: Admin, limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, Any]]:
    del admin
    async with SessionFactory() as session:
        rows = (await session.execute(select(TranslationRating, User, Release).join(User, User.id == TranslationRating.user_id).join(Release, Release.id == TranslationRating.release_id).order_by(TranslationRating.created_at.desc()).limit(limit))).all()
        return [{"id": str(item.id), "release_id": str(item.release_id), "release_label": release.chapter_label, "score": item.score, "feedback": item.feedback, "status": item.status, "vip_snapshot": item.vip_snapshot, "telegram_id": user.telegram_id, "anonymous_id": user.anonymous_id, "created_at": _iso(item.created_at)} for item, user, release in rows]


@router.post("/ratings/{rating_id}/workflow")
async def rating_workflow(rating_id: UUID, payload: RatingWorkflow, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        item = await session.get(TranslationRating, rating_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Оценка не найдена")
        old = item.status
        item.status = payload.status
        session.add(TranslationRatingStatusHistory(rating_id=item.id, old_status=old, new_status=payload.status, admin_telegram_id=admin.telegram_id, note=payload.note))
        await session.commit()
        return {"ok": True}


@router.get("/reports")
async def reports(admin: Admin, limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, Any]]:
    del admin
    async with SessionFactory() as session:
        rows = (await session.execute(select(Report, User).join(User, User.id == Report.user_id).order_by(Report.created_at.desc()).limit(limit))).all()
        return [{"id": str(item.id), "target_type": item.target_type, "title_id": str(item.title_id) if item.title_id else None, "release_id": str(item.release_id) if item.release_id else None, "category": item.category, "status": item.status, "description": item.description, "telegram_id": user.telegram_id, "anonymous_id": user.anonymous_id, "created_at": _iso(item.created_at)} for item, user in rows]


@router.post("/reports/{report_id}")
async def update_report(report_id: UUID, payload: ReportUpdate, admin: Admin) -> dict[str, Any]:
    settings = get_settings()
    async with SessionFactory() as session:
        item = await session.get(Report, report_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Жалоба не найдена")
        item.status = payload.status
        item.assigned_admin_id = admin.telegram_id
        user = await session.get(User, item.user_id)
        if payload.reply:
            session.add(ReportMessage(report_id=item.id, sender_type="admin", sender_admin_id=admin.telegram_id, body=payload.reply))
        session.add(AuditLog(actor_telegram_id=admin.telegram_id, action="report.updated", entity_type="report", entity_id=str(item.id), payload={"status": payload.status, "replied": bool(payload.reply)}))
        await session.commit()
    if user and payload.reply:
        bot = create_bot(settings)
        try:
            await bot.send_message(user.telegram_id, f"📋 <b>REPORT UPDATE</b>\n\nStatus: <b>{payload.status.replace('_', ' ').title()}</b>\n\n{payload.reply}")
        finally:
            await bot.session.close()
    return {"ok": True}


@router.get("/moderation-rules")
async def moderation_rules(admin: Admin) -> list[dict[str, Any]]:
    del admin
    async with SessionFactory() as session:
        rows = list((await session.execute(select(ModerationRule).order_by(ModerationRule.category, ModerationRule.code))).scalars())
        return [{"id": str(item.id), "code": item.code, "category": item.category, "replacement": item.replacement, "is_active": item.is_active, "comments": item.applies_to_comments, "nicknames": item.applies_to_nicknames, "feedback": item.applies_to_feedback} for item in rows]


@router.post("/moderation-rules/{rule_id}/toggle")
async def toggle_moderation_rule(rule_id: UUID, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        item = await session.get(ModerationRule, rule_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Правило не найдено")
        item.is_active = not item.is_active
        session.add(AuditLog(actor_telegram_id=admin.telegram_id, action="moderation_rule.toggled", entity_type="moderation_rule", entity_id=str(item.id), payload={"is_active": item.is_active}))
        await session.commit()
        return {"ok": True, "is_active": item.is_active}


@router.get("/boosty")
async def boosty_summary(admin: Admin) -> dict[str, Any]:
    del admin
    async with SessionFactory() as session:
        latest = (await session.execute(select(BoostySyncRun).order_by(BoostySyncRun.started_at.desc()).limit(1))).scalar_one_or_none()
        return {"active_vip": await _count(session, BoostyLink, BoostyLink.status == "active_vip"), "grace": await _count(session, BoostyLink, BoostyLink.status == "grace_period"), "expired": await _count(session, BoostyLink, BoostyLink.status == "expired"), "unverified": await _count(session, BoostyLink, BoostyLink.status == "unverified"), "last_sync": ({"status": latest.status, "started_at": _iso(latest.started_at), "finished_at": _iso(latest.finished_at), "scanned": latest.scanned_count, "changed": latest.changed_count, "errors": latest.error_count} if latest else None)}


@router.get("/broadcasts")
async def broadcasts(admin: Admin, limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, Any]]:
    del admin
    async with SessionFactory() as session:
        rows = list((await session.execute(select(Broadcast).order_by(Broadcast.created_at.desc()).limit(limit))).scalars())
        return [{"id": str(item.id), "status": item.status, "audience_type": item.audience_type, "text": item.text, "scheduled_at": _iso(item.scheduled_at), "total_count": item.total_count, "sent_count": item.sent_count, "failed_count": item.failed_count, "skipped_count": item.skipped_count, "created_at": _iso(item.created_at)} for item in rows]


@router.post("/broadcasts", status_code=201)
async def create_broadcast(payload: BroadcastCreate, admin: Admin) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    scheduled = now if payload.send_now else payload.scheduled_at
    state = "scheduled" if scheduled else "draft"
    async with SessionFactory() as session:
        item = Broadcast(status=state, audience_type=payload.audience_type, title_id=payload.title_id, text=payload.text, button_text=payload.button_text, button_url=payload.button_url, scheduled_at=scheduled, selected_user_ids=[str(value) for value in payload.selected_user_ids], created_by_admin_id=admin.telegram_id)
        session.add(item)
        await session.flush()
        session.add(AuditLog(actor_telegram_id=admin.telegram_id, action="broadcast.created", entity_type="broadcast", entity_id=str(item.id), payload={"audience": item.audience_type, "status": state}))
        await session.commit()
        return {"id": str(item.id), "status": item.status}


@router.post("/broadcasts/{broadcast_id}/photo")
async def upload_broadcast_photo(broadcast_id: UUID, admin: Admin, file: UploadFile = File(...)) -> dict[str, Any]:
    settings = get_settings()
    filename = Path(file.filename or "broadcast.jpg").name
    content_type = file.content_type or "image/jpeg"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Нужно загрузить изображение")
    temp = tempfile.NamedTemporaryFile(suffix=Path(filename).suffix or ".jpg", delete=False)
    temp.close()
    path = Path(temp.name)
    size = 0
    try:
        with path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.user_upload_max_bytes:
                    raise HTTPException(status_code=413, detail="Изображение превышает 20 МБ")
                destination.write(chunk)
        digest = _sha256(path)
        key = f"admin/broadcasts/{broadcast_id}/{uuid4().hex}-{filename}"
        storage = S3Storage(settings)
        with path.open("rb") as stream:
            stored = await asyncio.to_thread(storage.upload_fileobj, stream, key, content_type)
        async with SessionFactory() as session:
            item = await session.get(Broadcast, broadcast_id)
            if item is None or item.status not in {"draft", "scheduled"}:
                await asyncio.to_thread(storage.delete, key)
                raise HTTPException(status_code=404, detail="Рассылка недоступна для изменения")
            item.photo_object_key = stored.key
            item.photo_content_type = content_type
            session.add(AdminUpload(object_key=stored.key, purpose="broadcast_photo", original_filename=filename, content_type=content_type, size_bytes=stored.size, sha256=digest, metadata_json={"broadcast_id": str(item.id)}, created_by_admin_id=admin.telegram_id))
            await session.commit()
            return {"ok": True, "size_bytes": stored.size, "sha256": digest}
    finally:
        path.unlink(missing_ok=True)


@router.get("/channel")
async def channel_settings(admin: Admin) -> dict[str, Any]:
    del admin
    settings = get_settings()
    async with SessionFactory() as session:
        return {"channel_username": settings.telegram_channel_username, "channel_posts_enabled": settings.channel_posts_enabled, "sent": await _count(session, ChannelPublication, ChannelPublication.status == "sent"), "failed": await _count(session, ChannelPublication, ChannelPublication.status == "failed")}


@router.post("/channel")
async def update_channel(payload: ChannelSettingsUpdate, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        for key, value in {"telegram_channel_username": payload.channel_username, "channel_posts_enabled": payload.channel_posts_enabled}.items():
            item = (await session.execute(select(SystemSetting).where(SystemSetting.key == key))).scalar_one_or_none()
            if item is None:
                session.add(SystemSetting(key=key, value={"value": value}, description="Admin override"))
            else:
                item.value = {"value": value}
            session.add(AuditLog(actor_telegram_id=admin.telegram_id, action="system_setting.updated", entity_type="system_setting", entity_id=key, payload={"value": value}))
        await session.commit()
        return {"ok": True, "restart_required": True}


@router.get("/files")
async def files(admin: Admin, limit: int = Query(default=200, ge=1, le=500)) -> list[dict[str, Any]]:
    del admin
    async with SessionFactory() as session:
        rows = list((await session.execute(select(FileVersion).order_by(FileVersion.created_at.desc()).limit(limit))).scalars())
        return [{"id": str(item.id), "release_file_id": str(item.release_file_id), "version": item.version, "filename": item.original_filename, "content_type": item.content_type, "size_bytes": item.size_bytes, "sha256": item.sha256, "telegram_cached": bool(item.telegram_file_id), "is_active": item.is_active, "created_at": _iso(item.created_at)} for item in rows]


@router.get("/audit")
async def audit(admin: Admin, limit: int = Query(default=200, ge=1, le=1000)) -> list[dict[str, Any]]:
    del admin
    async with SessionFactory() as session:
        rows = list((await session.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))).scalars())
        return [{"id": str(item.id), "actor_telegram_id": item.actor_telegram_id, "action": item.action, "entity_type": item.entity_type, "entity_id": item.entity_id, "payload": item.payload, "created_at": _iso(item.created_at)} for item in rows]


@router.get("/settings")
async def system_settings(admin: Admin) -> list[dict[str, Any]]:
    del admin
    async with SessionFactory() as session:
        rows = list((await session.execute(select(SystemSetting).order_by(SystemSetting.key))).scalars())
        return [{"key": item.key, "value": item.value, "description": item.description, "updated_at": _iso(item.updated_at)} for item in rows]


@router.put("/settings/{key}")
async def update_setting(key: str, payload: SystemSettingUpdate, admin: Admin) -> dict[str, Any]:
    async with SessionFactory() as session:
        item = (await session.execute(select(SystemSetting).where(SystemSetting.key == key))).scalar_one_or_none()
        if item is None:
            session.add(SystemSetting(key=key, value=payload.value, description=payload.description))
        else:
            item.value = payload.value
            item.description = payload.description
        session.add(AuditLog(actor_telegram_id=admin.telegram_id, action="system_setting.updated", entity_type="system_setting", entity_id=key, payload={"value": payload.value}))
        await session.commit()
        return {"ok": True}
