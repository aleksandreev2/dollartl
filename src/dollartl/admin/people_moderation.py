from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_, select

from dollartl.admin.people_common import Admin, iso, page_meta
from dollartl.db.community_models import Comment, Report, TranslationRating
from dollartl.db.models import Release, Title, User
from dollartl.db.session import SessionFactory

router = APIRouter()


@router.get("/moderation/comments")
async def moderation_comments(
    admin: Admin,
    q: str = Query(default="", max_length=160),
    state: str = Query(default="active", max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=10, le=100),
) -> dict[str, Any]:
    del admin
    filters = []
    if state == "active":
        filters.append(Comment.is_deleted.is_(False))
    elif state == "deleted":
        filters.append(Comment.is_deleted.is_(True))
    elif state != "all":
        raise HTTPException(status_code=400, detail="Unknown comment state")
    normalized = q.strip().lstrip("@")
    if normalized:
        pattern = f"%{normalized}%"
        clauses = [
            Comment.public_body.ilike(pattern),
            Comment.original_body.ilike(pattern),
            User.telegram_username.ilike(pattern),
        ]
        if normalized.isdigit():
            value = int(normalized)
            clauses.extend([User.telegram_id == value, User.anonymous_id == value])
        filters.append(or_(*clauses))
    async with SessionFactory() as session:
        total = int(
            (
                await session.execute(
                    select(func.count(Comment.id))
                    .join(User, User.id == Comment.user_id)
                    .where(*filters)
                )
            ).scalar_one()
        )
        rows = (
            await session.execute(
                select(Comment, User)
                .join(User, User.id == Comment.user_id)
                .where(*filters)
                .order_by(Comment.created_at.desc(), Comment.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    return {
        **page_meta(total=total, page=page, page_size=page_size),
        "items": [
            {
                "id": str(item.id),
                "user_id": str(user.id),
                "anonymous_id": user.anonymous_id,
                "telegram_id": user.telegram_id,
                "telegram_username": user.telegram_username,
                "target_type": item.target_type,
                "original_body": item.original_body,
                "public_body": item.public_body,
                "replacement_count": item.replacement_count,
                "vip_snapshot": item.vip_snapshot,
                "is_deleted": item.is_deleted,
                "created_at": iso(item.created_at),
            }
            for item, user in rows
        ],
    }


@router.get("/moderation/ratings")
async def moderation_ratings(
    admin: Admin,
    q: str = Query(default="", max_length=160),
    status: str = Query(default="new", max_length=30),
    score: int | None = Query(default=None, ge=1, le=5),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=10, le=100),
) -> dict[str, Any]:
    del admin
    filters = [TranslationRating.is_deleted.is_(False)]
    if status != "all":
        filters.append(TranslationRating.status == status)
    if score is not None:
        filters.append(TranslationRating.score == score)
    normalized = q.strip().lstrip("@")
    if normalized:
        pattern = f"%{normalized}%"
        clauses = [
            TranslationRating.feedback.ilike(pattern),
            User.telegram_username.ilike(pattern),
            Title.english_title.ilike(pattern),
            Title.original_title.ilike(pattern),
        ]
        if normalized.isdigit():
            value = int(normalized)
            clauses.extend([User.telegram_id == value, User.anonymous_id == value])
        filters.append(or_(*clauses))
    async with SessionFactory() as session:
        total = int(
            (
                await session.execute(
                    select(func.count(TranslationRating.id))
                    .join(User, User.id == TranslationRating.user_id)
                    .join(Release, Release.id == TranslationRating.release_id)
                    .join(Title, Title.id == Release.title_id)
                    .where(*filters)
                )
            ).scalar_one()
        )
        rows = (
            await session.execute(
                select(TranslationRating, User, Release, Title)
                .join(User, User.id == TranslationRating.user_id)
                .join(Release, Release.id == TranslationRating.release_id)
                .join(Title, Title.id == Release.title_id)
                .where(*filters)
                .order_by(
                    TranslationRating.created_at.desc(),
                    TranslationRating.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    return {
        **page_meta(total=total, page=page, page_size=page_size),
        "items": [
            {
                "id": str(item.id),
                "user_id": str(user.id),
                "anonymous_id": user.anonymous_id,
                "telegram_id": user.telegram_id,
                "telegram_username": user.telegram_username,
                "title": title.english_title,
                "release_id": str(release.id),
                "release_label": release.chapter_label,
                "score": item.score,
                "feedback": item.feedback,
                "status": item.status,
                "vip_snapshot": item.vip_snapshot,
                "created_at": iso(item.created_at),
            }
            for item, user, release, title in rows
        ],
    }


@router.get("/moderation/reports")
async def moderation_reports(
    admin: Admin,
    q: str = Query(default="", max_length=160),
    status: str = Query(default="open", max_length=30),
    category: str = Query(default="all", max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=10, le=100),
) -> dict[str, Any]:
    del admin
    filters = []
    if status != "all":
        filters.append(Report.status == status)
    if category != "all":
        filters.append(Report.category == category)
    normalized = q.strip().lstrip("@")
    if normalized:
        pattern = f"%{normalized}%"
        clauses = [
            Report.description.ilike(pattern),
            Report.category.ilike(pattern),
            User.telegram_username.ilike(pattern),
        ]
        if normalized.isdigit():
            value = int(normalized)
            clauses.extend([User.telegram_id == value, User.anonymous_id == value])
        filters.append(or_(*clauses))
    async with SessionFactory() as session:
        total = int(
            (
                await session.execute(
                    select(func.count(Report.id))
                    .join(User, User.id == Report.user_id)
                    .where(*filters)
                )
            ).scalar_one()
        )
        rows = (
            await session.execute(
                select(Report, User)
                .join(User, User.id == Report.user_id)
                .where(*filters)
                .order_by(Report.created_at.desc(), Report.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        categories = [
            str(value)
            for value in (
                await session.execute(
                    select(Report.category).distinct().order_by(Report.category)
                )
            ).scalars()
        ]
    return {
        **page_meta(total=total, page=page, page_size=page_size),
        "categories": categories,
        "items": [
            {
                "id": str(item.id),
                "user_id": str(user.id),
                "anonymous_id": user.anonymous_id,
                "telegram_id": user.telegram_id,
                "telegram_username": user.telegram_username,
                "target_type": item.target_type,
                "category": item.category,
                "status": item.status,
                "description": item.description,
                "assigned_admin_id": item.assigned_admin_id,
                "created_at": iso(item.created_at),
            }
            for item, user in rows
        ],
    }
