from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from dollartl.config import Settings
from dollartl.db.boosty_models import (
    BoostyAccessEvent,
    BoostyAccessPeriod,
    BoostyLink,
)
from dollartl.db.models import User
from dollartl.integrations.boosty_types import BoostyMembership


@dataclass(frozen=True, slots=True)
class BoostyStatus:
    status: str
    boosty_username: str | None = None
    tier_name: str | None = None
    grace_ends_at: datetime | None = None
    membership_expires_at: datetime | None = None
    last_checked_at: datetime | None = None
    last_error_message: str | None = None

    @property
    def has_download_access(self) -> bool:
        if self.status == "active_vip":
            return True
        return (
            self.status == "grace_period"
            and self.grace_ends_at is not None
            and self.grace_ends_at > datetime.now(timezone.utc)
        )


class BoostyServiceBase:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def get_link(self, user_id: UUID) -> BoostyLink | None:
        return (
            await self.session.execute(
                select(BoostyLink).where(BoostyLink.user_id == user_id)
            )
        ).scalar_one_or_none()

    async def get_status(self, user_id: UUID) -> BoostyStatus:
        link = await self.get_link(user_id)
        if link is None:
            return BoostyStatus(status="unverified")
        return BoostyStatus(
            status=link.status,
            boosty_username=link.boosty_username,
            tier_name=link.tier_name,
            grace_ends_at=link.grace_ends_at,
            membership_expires_at=link.membership_expires_at,
            last_checked_at=link.last_checked_at,
            last_error_message=link.last_error_message,
        )

    async def can_download(self, user: User, admin_telegram_id: int) -> bool:
        if user.telegram_id == admin_telegram_id:
            return True
        thanked = (
            await self.session.execute(
                text(
                    "SELECT download_thanks_at FROM user_settings "
                    "WHERE user_id = :user_id"
                ),
                {"user_id": user.id},
            )
        ).scalar_one_or_none()
        if thanked is None:
            return False
        if user.manual_download_access:
            return True
        return (await self.get_status(user.id)).has_download_access

    def _eligible(self, membership: BoostyMembership | None) -> bool:
        return bool(
            membership is not None
            and membership.active
            and membership.tier_id == self.settings.boosty_tier_id
        )

    def _apply_membership_fields(
        self, link: BoostyLink, membership: BoostyMembership | None
    ) -> None:
        if membership is None:
            link.tier_id = None
            link.tier_name = None
            link.membership_expires_at = None
            return
        link.boosty_username = membership.identity.username or link.boosty_username
        link.tier_id = membership.tier_id
        link.tier_name = membership.tier_name
        link.membership_expires_at = membership.expires_at

    async def _transition(
        self,
        link: BoostyLink,
        status: str,
        *,
        reason: str,
        sync_run_id: UUID | None,
        event_type: str | None,
        event_payload: dict[str, object],
    ) -> None:
        if link.status == status and link.access_revision > 0:
            return
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(BoostyAccessPeriod)
            .where(
                BoostyAccessPeriod.boosty_link_id == link.id,
                BoostyAccessPeriod.ends_at.is_(None),
            )
            .values(ends_at=now)
        )
        link.status = status
        link.access_revision += 1
        self.session.add(
            BoostyAccessPeriod(
                boosty_link_id=link.id,
                user_id=link.user_id,
                status=status,
                starts_at=now,
                reason=reason,
                sync_run_id=sync_run_id,
            )
        )
        if event_type:
            await self.session.execute(
                insert(BoostyAccessEvent)
                .values(
                    boosty_link_id=link.id,
                    user_id=link.user_id,
                    access_revision=link.access_revision,
                    event_type=event_type,
                    payload=event_payload,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        BoostyAccessEvent.boosty_link_id,
                        BoostyAccessEvent.access_revision,
                        BoostyAccessEvent.event_type,
                    ]
                )
            )
