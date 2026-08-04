from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from dollartl.db.boosty_models import BoostyLink
from dollartl.db.models import AuditLog, User
from dollartl.services.boosty_base import BoostyServiceBase


class BoostyAdminMixin(BoostyServiceBase):
    async def manual_link(
        self,
        *,
        user: User,
        boosty_user_id: str,
        boosty_username: str | None,
        active: bool,
        admin_telegram_id: int,
    ) -> BoostyLink:
        conflict = (
            await self.session.execute(
                select(BoostyLink).where(
                    BoostyLink.boosty_user_id == boosty_user_id,
                    BoostyLink.user_id != user.id,
                )
            )
        ).scalar_one_or_none()
        if conflict is not None:
            raise ValueError("Boosty account is already linked to another Telegram user")
        link = await self.get_link(user.id)
        if link is None:
            link = BoostyLink(user_id=user.id, status="unverified")
            self.session.add(link)
            await self.session.flush()
        link.boosty_user_id = boosty_user_id
        link.boosty_username = boosty_username
        link.verified_at = datetime.now(timezone.utc)
        await self._transition(
            link,
            "active_vip" if active else "expired",
            reason="manual_admin_link",
            sync_run_id=None,
            event_type="verified" if active else "verification_ineligible",
            event_payload={"boosty_username": boosty_username},
        )
        self.session.add(
            AuditLog(
                actor_telegram_id=admin_telegram_id,
                action="boosty.manual_link",
                entity_type="user",
                entity_id=str(user.id),
                payload={"boosty_user_id": boosty_user_id, "active": active},
            )
        )
        await self.session.commit()
        return link

    async def unlink(self, *, user: User, admin_telegram_id: int) -> bool:
        link = await self.get_link(user.id)
        if link is None:
            return False
        await self.session.delete(link)
        self.session.add(
            AuditLog(
                actor_telegram_id=admin_telegram_id,
                action="boosty.unlinked",
                entity_type="user",
                entity_id=str(user.id),
                payload={},
            )
        )
        await self.session.commit()
        return True
