from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from dollartl.db.boosty_models import (
    BoostyAccessEvent,
    BoostyLink,
    BoostyProviderState,
    BoostySyncError,
    BoostySyncRun,
)
from dollartl.integrations.boosty_types import BoostyMembership
from dollartl.services.boosty_base import BoostyServiceBase


class BoostySyncMixin(BoostyServiceBase):
    async def start_sync_run(self, run_type: str) -> BoostySyncRun:
        run = BoostySyncRun(run_type=run_type, status="running")
        self.session.add(run)
        await self.session.commit()
        return run

    async def finish_sync_run(
        self,
        run: BoostySyncRun,
        *,
        status: str,
        scanned_count: int = 0,
        matched_count: int = 0,
        changed_count: int = 0,
        error_count: int = 0,
        metadata: dict[str, object] | None = None,
    ) -> None:
        persisted = await self.session.get(BoostySyncRun, run.id)
        if persisted is None:
            return
        persisted.status = status
        persisted.finished_at = datetime.now(timezone.utc)
        persisted.scanned_count = scanned_count
        persisted.matched_count = matched_count
        persisted.changed_count = changed_count
        persisted.error_count = error_count
        persisted.metadata_json = dict(metadata or {})
        await self.session.commit()

    async def record_sync_error(
        self,
        run: BoostySyncRun,
        *,
        code: str,
        message: str,
        user_id: UUID | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        self.session.add(
            BoostySyncError(
                sync_run_id=run.id,
                user_id=user_id,
                error_code=code,
                message=message[:4000],
                details=dict(details or {}),
            )
        )
        await self.session.commit()

    async def synchronize_memberships(
        self,
        memberships: dict[str, BoostyMembership],
        *,
        sync_run_id: UUID,
    ) -> int:
        links = list(
            (
                await self.session.execute(
                    select(BoostyLink).where(BoostyLink.boosty_user_id.is_not(None))
                )
            ).scalars()
        )
        changed = 0
        now = datetime.now(timezone.utc)
        for link in links:
            membership = memberships.get(str(link.boosty_user_id))
            link.last_checked_at = now
            link.last_successful_check_at = now
            link.last_error_code = None
            link.last_error_message = None
            self._apply_membership_fields(link, membership)
            if self._eligible(membership):
                if link.status != "active_vip":
                    await self._transition(
                        link,
                        "active_vip",
                        reason="membership_restored",
                        sync_run_id=sync_run_id,
                        event_type="access_restored",
                        event_payload={"boosty_username": link.boosty_username},
                    )
                    changed += 1
                link.grace_started_at = None
                link.grace_ends_at = None
                continue

            if link.status == "active_vip":
                link.grace_started_at = now
                link.grace_ends_at = now + timedelta(days=self.settings.boosty_grace_days)
                await self._transition(
                    link,
                    "grace_period",
                    reason="membership_not_confirmed",
                    sync_run_id=sync_run_id,
                    event_type="grace_started",
                    event_payload={"grace_ends_at": link.grace_ends_at.isoformat()},
                )
                changed += 1
            elif link.status == "grace_period":
                if link.grace_ends_at is not None and link.grace_ends_at <= now:
                    await self._transition(
                        link,
                        "expired",
                        reason="grace_period_expired",
                        sync_run_id=sync_run_id,
                        event_type="access_expired",
                        event_payload={},
                    )
                    changed += 1
            elif link.status in {"unverified", "verification_error"}:
                await self._transition(
                    link,
                    "expired",
                    reason="membership_ineligible",
                    sync_run_id=sync_run_id,
                    event_type=None,
                    event_payload={},
                )
                changed += 1
        await self.session.commit()
        return changed

    async def provider_call_allowed(self) -> bool:
        state = (
            await self.session.execute(
                select(BoostyProviderState).where(
                    BoostyProviderState.singleton_key == "primary"
                )
            )
        ).scalar_one_or_none()
        if state is None or state.circuit_open_until is None:
            return True
        return state.circuit_open_until <= datetime.now(timezone.utc)

    async def record_provider_success(self) -> None:
        now = datetime.now(timezone.utc)
        await self.session.execute(
            insert(BoostyProviderState)
            .values(
                singleton_key="primary",
                consecutive_failures=0,
                circuit_open_until=None,
                last_success_at=now,
                last_error_code=None,
                last_error_message=None,
            )
            .on_conflict_do_update(
                index_elements=[BoostyProviderState.singleton_key],
                set_={
                    "consecutive_failures": 0,
                    "circuit_open_until": None,
                    "last_success_at": now,
                    "last_error_code": None,
                    "last_error_message": None,
                    "updated_at": now,
                },
            )
        )
        await self.session.commit()

    async def record_provider_failure(self, code: str, message: str) -> None:
        now = datetime.now(timezone.utc)
        state = (
            await self.session.execute(
                select(BoostyProviderState)
                .where(BoostyProviderState.singleton_key == "primary")
                .with_for_update()
            )
        ).scalar_one_or_none()
        if state is None:
            state = BoostyProviderState(singleton_key="primary")
            self.session.add(state)
            await self.session.flush()
        state.consecutive_failures += 1
        state.last_failure_at = now
        state.last_error_code = code
        state.last_error_message = message[:4000]
        if state.consecutive_failures >= self.settings.boosty_circuit_breaker_failures:
            state.circuit_open_until = now + timedelta(
                seconds=self.settings.boosty_circuit_breaker_seconds
            )
        await self.session.execute(
            update(BoostyLink).values(
                last_checked_at=now,
                last_error_code=code,
                last_error_message=message[:4000],
            )
        )
        await self.session.commit()

    async def expire_grace_periods(self) -> int:
        now = datetime.now(timezone.utc)
        links = list(
            (
                await self.session.execute(
                    select(BoostyLink).where(
                        BoostyLink.status == "grace_period",
                        BoostyLink.grace_ends_at.is_not(None),
                        BoostyLink.grace_ends_at <= now,
                    )
                )
            ).scalars()
        )
        for link in links:
            await self._transition(
                link,
                "expired",
                reason="grace_period_expired",
                sync_run_id=None,
                event_type="access_expired",
                event_payload={},
            )
        await self.session.commit()
        return len(links)

    async def next_access_event(self) -> BoostyAccessEvent | None:
        event = (
            await self.session.execute(
                select(BoostyAccessEvent)
                .where(BoostyAccessEvent.sent_at.is_(None))
                .order_by(BoostyAccessEvent.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(1)
            )
        ).scalar_one_or_none()
        if event is not None:
            event.attempts += 1
            await self.session.commit()
        return event

    async def mark_event_sent(self, event_id: UUID) -> None:
        await self.session.execute(
            update(BoostyAccessEvent)
            .where(BoostyAccessEvent.id == event_id)
            .values(sent_at=datetime.now(timezone.utc), last_error=None)
        )
        await self.session.commit()

    async def mark_event_failed(self, event_id: UUID, error: str) -> None:
        await self.session.execute(
            update(BoostyAccessEvent)
            .where(BoostyAccessEvent.id == event_id)
            .values(last_error=error[:4000])
        )
        await self.session.commit()
