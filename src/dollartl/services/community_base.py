from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from dollartl.config import Settings
from dollartl.db.boosty_models import BoostyLink
from dollartl.db.models import User, UserSettings


class CommunityServiceBase:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def display_name(self, user_id: UUID) -> tuple[str, bool]:
        row = (
            await self.session.execute(
                select(User, UserSettings, BoostyLink)
                .join(UserSettings, UserSettings.user_id == User.id)
                .outerjoin(BoostyLink, BoostyLink.user_id == User.id)
                .where(User.id == user_id)
            )
        ).one()
        user, settings, boosty = row
        name = settings.display_name or user.anonymous_name
        vip = False
        if boosty is not None:
            vip = boosty.status == "active_vip" or (
                boosty.status == "grace_period"
                and boosty.grace_ends_at is not None
                and boosty.grace_ends_at > datetime.now(timezone.utc)
            )
        return name, vip

    async def has_download_thanks(self, user_id: UUID) -> bool:
        value = (
            await self.session.execute(
                text(
                    "SELECT download_thanks_at FROM user_settings "
                    "WHERE user_id = :user_id"
                ),
                {"user_id": user_id},
            )
        ).scalar_one_or_none()
        return value is not None

    async def record_download_thanks(self, user_id: UUID) -> bool:
        result = await self.session.execute(
            text(
                "UPDATE user_settings SET download_thanks_at = :now, updated_at = :now "
                "WHERE user_id = :user_id AND download_thanks_at IS NULL"
            ),
            {"user_id": user_id, "now": datetime.now(timezone.utc)},
        )
        await self.session.commit()
        return bool(result.rowcount)
