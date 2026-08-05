from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from sqlalchemy import or_, select

from dollartl.admin.people_common import Admin, SelectedUsersRequest
from dollartl.config import get_settings
from dollartl.db.models import Ban, User, UserConsent
from dollartl.db.session import SessionFactory
from dollartl.services.access import ADULT_CONSENT_TYPE

router = APIRouter()


@router.post("/selected-users/preview")
async def selected_users_preview(
    payload: SelectedUsersRequest,
    admin: Admin,
) -> dict[str, Any]:
    del admin
    settings = get_settings()
    now = datetime.now(timezone.utc)
    requested = list(dict.fromkeys(payload.user_ids))
    async with SessionFactory() as session:
        users = list(
            (
                await session.execute(select(User).where(User.id.in_(requested)))
            ).scalars()
        )
        user_ids = [item.id for item in users]
        bans = set(
            (
                await session.execute(
                    select(Ban.user_id).where(
                        Ban.user_id.in_(user_ids) if user_ids else False,
                        Ban.is_active.is_(True),
                        or_(
                            Ban.ban_type == "permanent",
                            Ban.expires_at.is_(None),
                            Ban.expires_at > now,
                        ),
                    )
                )
            ).scalars()
        )
        consents = set(
            (
                await session.execute(
                    select(UserConsent.user_id).where(
                        UserConsent.user_id.in_(user_ids) if user_ids else False,
                        UserConsent.consent_type == ADULT_CONSENT_TYPE,
                        UserConsent.version == settings.adult_consent_version,
                    )
                )
            ).scalars()
        )
    found = {item.id for item in users}
    items = [
        {
            "id": str(item.id),
            "anonymous_id": item.anonymous_id,
            "telegram_id": item.telegram_id,
            "telegram_username": item.telegram_username,
            "is_active": item.is_active,
            "banned": item.id in bans,
            "adult_consent": item.id in consents,
            "eligible": item.is_active and item.id not in bans,
        }
        for item in users
    ]
    return {
        "requested": len(requested),
        "found": len(users),
        "missing": len(set(requested) - found),
        "eligible": sum(1 for item in items if item["eligible"]),
        "inactive": sum(1 for item in items if not item["is_active"]),
        "banned": sum(1 for item in items if item["banned"]),
        "without_consent": sum(1 for item in items if not item["adult_consent"]),
        "items": items,
    }
