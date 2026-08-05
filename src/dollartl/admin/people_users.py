from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_, select

from dollartl.admin.people_common import Admin, active_ban_exists, iso, page_meta
from dollartl.db.boosty_models import BoostyLink
from dollartl.db.models import Ban, NotificationPreference, User, UserSettings
from dollartl.db.session import SessionFactory

router = APIRouter()


@router.get("/users/workbench")
async def users_workbench(
    admin: Admin,
    q: str = Query(default="", max_length=120),
    access: str = Query(default="all", max_length=30),
    state: str = Query(default="all", max_length=30),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=10, le=100),
) -> dict[str, Any]:
    del admin
    now = datetime.now(timezone.utc)
    normalized = q.strip().lstrip("@")
    filters = []
    if normalized:
        pattern = f"%{normalized}%"
        clauses = [
            User.telegram_username.ilike(pattern),
            User.telegram_first_name.ilike(pattern),
            User.telegram_last_name.ilike(pattern),
            UserSettings.display_name.ilike(pattern),
        ]
        numeric = normalized.removeprefix("Anonymous ").strip()
        if numeric.isdigit():
            value = int(numeric)
            clauses.extend([User.telegram_id == value, User.anonymous_id == value])
        filters.append(or_(*clauses))

    ban_exists = active_ban_exists(now)
    if state == "active":
        filters.extend([User.is_active.is_(True), ~ban_exists])
    elif state == "inactive":
        filters.append(User.is_active.is_(False))
    elif state == "banned":
        filters.append(ban_exists)
    elif state != "all":
        raise HTTPException(status_code=400, detail="Unknown user state filter")

    eligible_boosty = or_(
        BoostyLink.status == "active_vip",
        (BoostyLink.status == "grace_period") & (BoostyLink.grace_ends_at > now),
    )
    if access == "vip":
        filters.append(BoostyLink.status == "active_vip")
    elif access == "grace":
        filters.extend(
            [BoostyLink.status == "grace_period", BoostyLink.grace_ends_at > now]
        )
    elif access == "manual":
        filters.append(User.manual_download_access.is_(True))
    elif access == "standard":
        filters.extend([User.manual_download_access.is_(False), ~eligible_boosty])
    elif access != "all":
        raise HTTPException(status_code=400, detail="Unknown access filter")

    async with SessionFactory() as session:
        joins = (
            select(User, UserSettings, NotificationPreference, BoostyLink)
            .outerjoin(UserSettings, UserSettings.user_id == User.id)
            .outerjoin(NotificationPreference, NotificationPreference.user_id == User.id)
            .outerjoin(BoostyLink, BoostyLink.user_id == User.id)
            .where(*filters)
        )
        total = int(
            (
                await session.execute(
                    select(func.count(User.id))
                    .outerjoin(UserSettings, UserSettings.user_id == User.id)
                    .outerjoin(BoostyLink, BoostyLink.user_id == User.id)
                    .where(*filters)
                )
            ).scalar_one()
        )
        rows = (
            await session.execute(
                joins.order_by(User.last_seen_at.desc(), User.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        user_ids = [user.id for user, *_ in rows]
        bans = list(
            (
                await session.execute(
                    select(Ban)
                    .where(
                        Ban.user_id.in_(user_ids) if user_ids else False,
                        Ban.is_active.is_(True),
                        or_(
                            Ban.ban_type == "permanent",
                            Ban.expires_at.is_(None),
                            Ban.expires_at > now,
                        ),
                    )
                    .order_by(Ban.created_at.desc())
                )
            ).scalars()
        )
        ban_by_user: dict[UUID, Ban] = {}
        for item in bans:
            ban_by_user.setdefault(item.user_id, item)

        summary_rows = (
            await session.execute(
                select(BoostyLink.status, func.count(BoostyLink.id)).group_by(
                    BoostyLink.status
                )
            )
        ).all()
        total_users = int(
            (await session.execute(select(func.count(User.id)))).scalar_one()
        )
        manual_users = int(
            (
                await session.execute(
                    select(func.count(User.id)).where(
                        User.manual_download_access.is_(True)
                    )
                )
            ).scalar_one()
        )
        banned_users = int(
            (
                await session.execute(
                    select(func.count(User.id)).where(active_ban_exists(now))
                )
            ).scalar_one()
        )

    return {
        **page_meta(total=total, page=page, page_size=page_size),
        "summary": {
            "users": total_users,
            "banned": banned_users,
            "manual": manual_users,
            **{str(key): int(value) for key, value in summary_rows},
        },
        "items": [
            {
                "id": str(user.id),
                "telegram_id": user.telegram_id,
                "telegram_username": user.telegram_username,
                "telegram_first_name": user.telegram_first_name,
                "telegram_last_name": user.telegram_last_name,
                "anonymous_id": user.anonymous_id,
                "display_name": preferences.display_name if preferences else None,
                "is_active": user.is_active,
                "manual_download_access": user.manual_download_access,
                "last_seen_at": iso(user.last_seen_at),
                "created_at": iso(user.created_at),
                "boosty_status": link.status if link else "unverified",
                "boosty_username": link.boosty_username if link else None,
                "grace_ends_at": iso(link.grace_ends_at) if link else None,
                "notifications": {
                    "new_titles": (
                        notification.new_title_announcements if notification else True
                    ),
                    "service": (
                        notification.service_notifications if notification else True
                    ),
                },
                "ban": (
                    {
                        "id": str(ban_by_user[user.id].id),
                        "type": ban_by_user[user.id].ban_type,
                        "reason": ban_by_user[user.id].public_reason,
                        "expires_at": iso(ban_by_user[user.id].expires_at),
                    }
                    if user.id in ban_by_user
                    else None
                ),
            }
            for user, preferences, notification, link in rows
        ],
    }
