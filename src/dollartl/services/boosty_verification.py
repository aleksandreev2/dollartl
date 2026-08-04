from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update

from dollartl.db.boosty_models import BoostyLink, BoostyVerificationCode
from dollartl.db.models import AuditLog
from dollartl.integrations.boosty_types import BoostyIdentity, BoostyMembership
from dollartl.services.boosty_base import BoostyServiceBase


class BoostyVerificationMixin(BoostyServiceBase):
    async def create_verification_code(self, user_id: UUID) -> BoostyVerificationCode:
        now = datetime.now(timezone.utc)
        existing = (
            await self.session.execute(
                select(BoostyVerificationCode)
                .where(
                    BoostyVerificationCode.user_id == user_id,
                    BoostyVerificationCode.status == "pending",
                    BoostyVerificationCode.expires_at > now,
                )
                .order_by(BoostyVerificationCode.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        await self.session.execute(
            update(BoostyVerificationCode)
            .where(
                BoostyVerificationCode.user_id == user_id,
                BoostyVerificationCode.status == "pending",
            )
            .values(status="expired", error_message="Superseded by a new verification code")
        )
        code = await self._unique_code()
        row = BoostyVerificationCode(
            user_id=user_id,
            code=code,
            status="pending",
            expires_at=now + timedelta(minutes=self.settings.boosty_code_ttl_minutes),
            force_check_requested_at=now,
        )
        self.session.add(row)
        self.session.add(
            AuditLog(
                actor_telegram_id=None,
                action="boosty.verification_code_created",
                entity_type="user",
                entity_id=str(user_id),
                payload={"expires_at": row.expires_at.isoformat()},
            )
        )
        await self.session.commit()
        return row

    async def _unique_code(self) -> str:
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(20):
            code = "DL-" + "".join(secrets.choice(alphabet) for _ in range(4))
            code += "-" + "".join(secrets.choice(alphabet) for _ in range(4))
            exists = (
                await self.session.execute(
                    select(BoostyVerificationCode.id).where(
                        BoostyVerificationCode.code == code
                    )
                )
            ).scalar_one_or_none()
            if exists is None:
                return code
        raise RuntimeError("Could not generate a unique Boosty verification code")

    async def request_immediate_check(self, user_id: UUID) -> bool:
        now = datetime.now(timezone.utc)
        code = (
            await self.session.execute(
                select(BoostyVerificationCode)
                .where(
                    BoostyVerificationCode.user_id == user_id,
                    BoostyVerificationCode.status == "pending",
                    BoostyVerificationCode.expires_at > now,
                )
                .order_by(BoostyVerificationCode.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if code is None:
            return False
        code.force_check_requested_at = now
        await self.session.commit()
        return True

    async def pending_codes(self, *, limit: int = 100) -> list[BoostyVerificationCode]:
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(BoostyVerificationCode)
            .where(
                BoostyVerificationCode.status == "pending",
                BoostyVerificationCode.expires_at <= now,
            )
            .values(status="expired", error_message="Verification code expired")
        )
        await self.session.commit()
        return list(
            (
                await self.session.execute(
                    select(BoostyVerificationCode)
                    .where(
                        BoostyVerificationCode.status == "pending",
                        BoostyVerificationCode.expires_at > now,
                    )
                    .order_by(
                        BoostyVerificationCode.force_check_requested_at.desc().nullslast(),
                        BoostyVerificationCode.created_at.asc(),
                    )
                    .limit(limit)
                )
            ).scalars()
        )

    async def mark_pending_codes_checked(self, codes: list[BoostyVerificationCode]) -> None:
        if not codes:
            return
        now = datetime.now(timezone.utc)
        ids = [item.id for item in codes]
        user_ids = [item.user_id for item in codes]
        await self.session.execute(
            update(BoostyVerificationCode)
            .where(BoostyVerificationCode.id.in_(ids))
            .values(
                attempts=BoostyVerificationCode.attempts + 1,
                last_checked_at=now,
                force_check_requested_at=None,
            )
        )
        await self.session.execute(
            update(BoostyLink)
            .where(
                BoostyLink.user_id.in_(user_ids),
                BoostyLink.status == "verification_error",
            )
            .values(
                status="unverified",
                last_checked_at=now,
                last_error_code=None,
                last_error_message=None,
            )
        )
        await self.session.commit()

    async def mark_verification_error(
        self, codes: list[BoostyVerificationCode], *, code: str, message: str
    ) -> None:
        now = datetime.now(timezone.utc)
        for item in codes:
            link = await self.get_link(item.user_id)
            if link is None:
                link = BoostyLink(user_id=item.user_id, status="verification_error")
                self.session.add(link)
            elif link.status not in {"unverified", "verification_error", "expired"}:
                continue
            else:
                link.status = "verification_error"
            link.last_checked_at = now
            link.last_error_code = code
            link.last_error_message = message[:4000]
        await self.session.commit()

    async def apply_verification_match(
        self,
        *,
        code_id: UUID,
        identity: BoostyIdentity,
        membership: BoostyMembership | None,
        sync_run_id: UUID,
    ) -> bool:
        now = datetime.now(timezone.utc)
        code = (
            await self.session.execute(
                select(BoostyVerificationCode)
                .where(BoostyVerificationCode.id == code_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if code is None or code.status != "pending" or code.expires_at <= now:
            return False
        conflict = (
            await self.session.execute(
                select(BoostyLink).where(
                    BoostyLink.boosty_user_id == identity.user_id,
                    BoostyLink.user_id != code.user_id,
                )
            )
        ).scalar_one_or_none()
        if conflict is not None:
            code.status = "conflict"
            code.detected_boosty_user_id = identity.user_id
            code.detected_boosty_username = identity.username
            code.error_message = "This Boosty account is already linked to another Telegram account."
            await self.session.commit()
            return False

        link = await self.get_link(code.user_id)
        if link is None:
            link = BoostyLink(user_id=code.user_id, status="unverified")
            self.session.add(link)
            await self.session.flush()
        link.boosty_user_id = identity.user_id
        link.boosty_username = identity.username
        link.verified_at = now
        link.last_checked_at = now
        link.last_successful_check_at = now
        link.last_error_code = None
        link.last_error_message = None

        eligible = self._eligible(membership)
        target_status = "active_vip" if eligible else "expired"
        event_type = "verified" if eligible else "verification_ineligible"
        await self._transition(
            link,
            target_status,
            reason="verification_matched",
            sync_run_id=sync_run_id,
            event_type=event_type,
            event_payload={
                "boosty_username": identity.username,
                "tier_name": membership.tier_name if membership else None,
            },
        )
        self._apply_membership_fields(link, membership)
        code.status = "matched"
        code.consumed_at = now
        code.detected_boosty_user_id = identity.user_id
        code.detected_boosty_username = identity.username
        code.error_message = None
        self.session.add(
            AuditLog(
                actor_telegram_id=None,
                action="boosty.account_linked",
                entity_type="user",
                entity_id=str(code.user_id),
                payload={
                    "boosty_user_id": identity.user_id,
                    "boosty_username": identity.username,
                    "eligible": eligible,
                },
            )
        )
        await self.session.commit()
        return True
