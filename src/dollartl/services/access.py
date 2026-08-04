from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from aiogram.types import User as TelegramUser
from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from dollartl.db.models import (
    AuditLog,
    Ban,
    BanHistory,
    NotificationPreference,
    User,
    UserConsent,
    UserSettings,
)

ADULT_CONSENT_TYPE = "adult_content"

BAN_REASON_TEMPLATES: dict[str, str] = {
    "rules": "Repeated violations of the bot rules.",
    "prohibited_title": "Submission of prohibited content.",
    "racism": "Repeated use of racist slurs or abusive language.",
    "spam": "Repeated spam or flooding.",
    "abuse": "Harassment or abusive behavior.",
    "unsafe_file": "Uploading a malicious or unsafe file.",
    "ban_evasion": "Attempting to evade a previous account restriction.",
    "false_information": "Deliberately providing false or misleading information.",
}


@dataclass(frozen=True, slots=True)
class AccessDecision:
    blocked: bool
    should_notify: bool = False
    ban_type: str | None = None
    expires_at: datetime | None = None
    public_reason: str | None = None


class AccessService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_user(self, telegram_user: TelegramUser) -> User:
        statement = (
            insert(User)
            .values(
                telegram_id=telegram_user.id,
                telegram_username=telegram_user.username,
                telegram_first_name=telegram_user.first_name,
                telegram_last_name=telegram_user.last_name,
                last_seen_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                index_elements=[User.telegram_id],
                set_={
                    "telegram_username": telegram_user.username,
                    "telegram_first_name": telegram_user.first_name,
                    "telegram_last_name": telegram_user.last_name,
                    "last_seen_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            .returning(User.id)
        )
        user_id = (await self.session.execute(statement)).scalar_one()
        await self.session.execute(
            insert(UserSettings)
            .values(user_id=user_id, locale="en")
            .on_conflict_do_nothing(index_elements=[UserSettings.user_id])
        )
        await self.session.execute(
            insert(NotificationPreference)
            .values(
                user_id=user_id,
                new_title_announcements=True,
                service_notifications=True,
            )
            .on_conflict_do_nothing(index_elements=[NotificationPreference.user_id])
        )
        await self.session.commit()
        user = await self.session.get(User, user_id)
        if user is None:
            raise RuntimeError("User upsert did not return a persisted user")
        return user

    async def has_consent(self, user_id: UUID, version: int) -> bool:
        statement = select(UserConsent.id).where(
            UserConsent.user_id == user_id,
            UserConsent.consent_type == ADULT_CONSENT_TYPE,
            UserConsent.version == version,
        )
        return (await self.session.execute(statement)).scalar_one_or_none() is not None

    async def accept_consent(self, user_id: UUID, version: int) -> None:
        await self.session.execute(
            insert(UserConsent)
            .values(
                user_id=user_id,
                consent_type=ADULT_CONSENT_TYPE,
                version=version,
                source="telegram_bot",
            )
            .on_conflict_do_nothing(
                index_elements=[
                    UserConsent.user_id,
                    UserConsent.consent_type,
                    UserConsent.version,
                ]
            )
        )
        self.session.add(
            AuditLog(
                actor_telegram_id=None,
                action="adult_consent.accepted",
                entity_type="user",
                entity_id=str(user_id),
                payload={"version": version, "source": "telegram_bot"},
            )
        )
        await self.session.commit()

    async def set_pending_deep_link(self, user_id: UUID, token: str) -> None:
        if not token or len(token) > 64:
            return
        await self.session.execute(
            update(UserSettings)
            .where(UserSettings.user_id == user_id)
            .values(pending_deep_link_token=token)
        )
        await self.session.commit()

    async def pop_pending_deep_link(self, user_id: UUID) -> str | None:
        settings = (
            await self.session.execute(
                select(UserSettings).where(UserSettings.user_id == user_id).with_for_update()
            )
        ).scalar_one_or_none()
        if settings is None:
            return None
        token = settings.pending_deep_link_token
        settings.pending_deep_link_token = None
        await self.session.commit()
        return token

    async def resolve_ban(
        self,
        user_id: UUID,
        *,
        notice_interval: timedelta,
        now: datetime | None = None,
    ) -> AccessDecision:
        current_time = now or datetime.now(timezone.utc)
        statement = (
            select(Ban)
            .where(Ban.user_id == user_id, Ban.is_active.is_(True))
            .order_by(Ban.created_at.desc())
            .limit(1)
        )
        ban = (await self.session.execute(statement)).scalar_one_or_none()
        if ban is None:
            return AccessDecision(blocked=False)

        if ban.ban_type == "temporary" and ban.expires_at is not None:
            if ban.expires_at <= current_time:
                ban.is_active = False
                ban.unbanned_at = current_time
                self.session.add(
                    BanHistory(
                        ban_id=ban.id,
                        action="expired",
                        actor_telegram_id=None,
                        details={"expired_at": current_time.isoformat()},
                    )
                )
                await self.session.commit()
                return AccessDecision(blocked=False)

        cutoff = current_time - notice_interval
        mark_notice = (
            update(Ban)
            .where(
                Ban.id == ban.id,
                Ban.is_active.is_(True),
                or_(Ban.last_notice_at.is_(None), Ban.last_notice_at <= cutoff),
            )
            .values(last_notice_at=current_time)
            .returning(Ban.id)
        )
        should_notify = (
            await self.session.execute(mark_notice)
        ).scalar_one_or_none() is not None
        await self.session.commit()
        return AccessDecision(
            blocked=True,
            should_notify=should_notify,
            ban_type=ban.ban_type,
            expires_at=ban.expires_at,
            public_reason=ban.public_reason,
        )

    async def toggle_new_title_notifications(self, user_id: UUID) -> bool:
        preference = (
            await self.session.execute(
                select(NotificationPreference).where(
                    NotificationPreference.user_id == user_id
                )
            )
        ).scalar_one()
        preference.new_title_announcements = not preference.new_title_announcements
        await self.session.commit()
        return preference.new_title_announcements

    async def get_new_title_notifications(self, user_id: UUID) -> bool:
        value = (
            await self.session.execute(
                select(NotificationPreference.new_title_announcements).where(
                    NotificationPreference.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        return True if value is None else value

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        return (
            await self.session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
        ).scalar_one_or_none()

    async def set_manual_download_access(
        self, *, target: User, enabled: bool, admin_telegram_id: int
    ) -> None:
        target.manual_download_access = enabled
        self.session.add(
            AuditLog(
                actor_telegram_id=admin_telegram_id,
                action="user.manual_download_access_changed",
                entity_type="user",
                entity_id=str(target.id),
                payload={"enabled": enabled, "target_telegram_id": target.telegram_id},
            )
        )
        await self.session.commit()

    async def create_ban(
        self,
        *,
        target: User,
        ban_type: str,
        public_reason: str,
        admin_telegram_id: int,
        expires_at: datetime | None,
        reason_template: str | None = None,
        internal_note: str | None = None,
    ) -> Ban:
        if ban_type not in {"temporary", "permanent"}:
            raise ValueError("Unsupported ban type")
        if ban_type == "temporary" and expires_at is None:
            raise ValueError("Temporary ban requires expires_at")
        if ban_type == "permanent":
            expires_at = None

        active_bans = (
            await self.session.execute(
                select(Ban).where(Ban.user_id == target.id, Ban.is_active.is_(True))
            )
        ).scalars()
        now = datetime.now(timezone.utc)
        for old_ban in active_bans:
            old_ban.is_active = False
            old_ban.unbanned_at = now
            old_ban.unbanned_by_admin_id = admin_telegram_id
            self.session.add(
                BanHistory(
                    ban_id=old_ban.id,
                    action="superseded",
                    actor_telegram_id=admin_telegram_id,
                    details={},
                )
            )

        ban = Ban(
            user_id=target.id,
            ban_type=ban_type,
            starts_at=now,
            expires_at=expires_at,
            public_reason=public_reason,
            reason_template=reason_template,
            internal_note=internal_note,
            is_active=True,
            created_by_admin_id=admin_telegram_id,
        )
        self.session.add(ban)
        await self.session.flush()
        self.session.add(
            BanHistory(
                ban_id=ban.id,
                action="created",
                actor_telegram_id=admin_telegram_id,
                details={
                    "ban_type": ban_type,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                    "public_reason": public_reason,
                    "reason_template": reason_template,
                },
            )
        )
        self.session.add(
            AuditLog(
                actor_telegram_id=admin_telegram_id,
                action="user.banned",
                entity_type="user",
                entity_id=str(target.id),
                payload={
                    "target_telegram_id": target.telegram_id,
                    "ban_type": ban_type,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                    "reason_template": reason_template,
                },
            )
        )
        await self.session.commit()
        return ban

    async def unban_user(
        self, *, target: User, admin_telegram_id: int, note: str | None = None
    ) -> int:
        bans = (
            await self.session.execute(
                select(Ban).where(Ban.user_id == target.id, Ban.is_active.is_(True))
            )
        ).scalars()
        now = datetime.now(timezone.utc)
        count = 0
        for ban in bans:
            count += 1
            ban.is_active = False
            ban.unbanned_at = now
            ban.unbanned_by_admin_id = admin_telegram_id
            self.session.add(
                BanHistory(
                    ban_id=ban.id,
                    action="manually_unbanned",
                    actor_telegram_id=admin_telegram_id,
                    details={"note": note},
                )
            )
        if count:
            self.session.add(
                AuditLog(
                    actor_telegram_id=admin_telegram_id,
                    action="user.unbanned",
                    entity_type="user",
                    entity_id=str(target.id),
                    payload={"target_telegram_id": target.telegram_id, "note": note},
                )
            )
        await self.session.commit()
        return count
