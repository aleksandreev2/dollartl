from __future__ import annotations

import logging
from datetime import datetime
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

from dollartl.config import Settings
from dollartl.db.models import User
from dollartl.db.session import SessionFactory
from dollartl.integrations.boosty import PrivateBoostyProvider
from dollartl.integrations.boosty_types import BoostyProviderError
from dollartl.services.boosty import BoostyService

logger = logging.getLogger(__name__)


async def process_pending_verifications(settings: Settings) -> bool:
    if not settings.boosty_enabled:
        return False
    async with SessionFactory() as session:
        service = BoostyService(session, settings)
        codes = await service.pending_codes(limit=settings.boosty_contacts_limit)
        if not codes or not await service.provider_call_allowed():
            return False
        run = await service.start_sync_run("verification")
        try:
            async with PrivateBoostyProvider(session, settings) as provider:
                matches = await provider.find_verification_codes({item.code for item in codes})
                memberships = await provider.list_memberships() if matches else {}
            await service.mark_pending_codes_checked(codes)
            changed = 0
            for item in codes:
                identity = matches.get(item.code)
                if identity is None:
                    continue
                membership = memberships.get(identity.user_id)
                applied = await service.apply_verification_match(
                    code_id=item.id,
                    identity=identity,
                    membership=membership,
                    sync_run_id=run.id,
                )
                changed += int(applied)
            await service.record_provider_success()
            await service.finish_sync_run(
                run,
                status="success",
                scanned_count=len(codes),
                matched_count=len(matches),
                changed_count=changed,
            )
            return True
        except BoostyProviderError as exc:
            await service.record_sync_error(run, code=exc.code, message=str(exc))
            await service.mark_verification_error(codes, code=exc.code, message=str(exc))
            await service.record_provider_failure(exc.code, str(exc))
            await service.finish_sync_run(run, status="failed", error_count=1)
            logger.warning("boosty_verification_failed", extra={"code": exc.code})
            return False
        except Exception as exc:
            await service.record_sync_error(
                run, code=type(exc).__name__, message=str(exc)
            )
            await service.mark_verification_error(
                codes, code=type(exc).__name__, message=str(exc)
            )
            await service.record_provider_failure(type(exc).__name__, str(exc))
            await service.finish_sync_run(run, status="failed", error_count=1)
            logger.exception("boosty_verification_failed")
            return False


async def synchronize_memberships(settings: Settings) -> bool:
    if not settings.boosty_enabled:
        return False
    async with SessionFactory() as session:
        service = BoostyService(session, settings)
        if not await service.provider_call_allowed():
            return False
        run = await service.start_sync_run("membership")
        try:
            async with PrivateBoostyProvider(session, settings) as provider:
                memberships = await provider.list_memberships()
            changed = await service.synchronize_memberships(
                memberships, sync_run_id=run.id
            )
            await service.record_provider_success()
            await service.finish_sync_run(
                run,
                status="success",
                scanned_count=len(memberships),
                changed_count=changed,
            )
            return True
        except BoostyProviderError as exc:
            await service.record_sync_error(run, code=exc.code, message=str(exc))
            await service.record_provider_failure(exc.code, str(exc))
            await service.finish_sync_run(run, status="failed", error_count=1)
            logger.warning("boosty_membership_sync_failed", extra={"code": exc.code})
            return False
        except Exception as exc:
            await service.record_sync_error(
                run, code=type(exc).__name__, message=str(exc)
            )
            await service.record_provider_failure(type(exc).__name__, str(exc))
            await service.finish_sync_run(run, status="failed", error_count=1)
            logger.exception("boosty_membership_sync_failed")
            return False


async def expire_grace_periods(settings: Settings) -> int:
    async with SessionFactory() as session:
        return await BoostyService(session, settings).expire_grace_periods()


async def deliver_next_access_event(bot: Bot, settings: Settings) -> bool:
    async with SessionFactory() as session:
        service = BoostyService(session, settings)
        event = await service.next_access_event()
        if event is None:
            return False
        user = await session.get(User, event.user_id)
        if user is None:
            await service.mark_event_sent(event.id)
            return True
        text = _event_text(event.event_type, event.payload, settings)
        try:
            await bot.send_message(user.telegram_id, text)
        except TelegramForbiddenError:
            await service.mark_event_sent(event.id)
            return True
        except Exception as exc:
            await service.mark_event_failed(event.id, f"{type(exc).__name__}: {exc}")
            return False
        await service.mark_event_sent(event.id)
        return True


def _event_text(event_type: str, payload: dict[str, object], settings: Settings) -> str:
    username = escape(str(payload.get("boosty_username") or "your Boosty account"))
    if event_type == "verified":
        tier = escape(str(payload.get("tier_name") or "eligible membership"))
        return (
            "✅ <b>BOOSTY MEMBERSHIP VERIFIED</b>\n\n"
            f"Boosty account: <b>{username}</b>\n"
            f"Membership: <b>{tier}</b>\n\n"
            "VIP access is active. All available PDF and EPUB releases are unlocked."
        )
    if event_type == "verification_ineligible":
        return (
            "⚠️ <b>MEMBERSHIP NOT ELIGIBLE</b>\n\n"
            f"Boosty account: <b>{username}</b>\n\n"
            "The account was linked, but the required membership is not active."
        )
    if event_type == "grace_started":
        raw = str(payload.get("grace_ends_at") or "")
        return (
            "⚠️ <b>BOOSTY MEMBERSHIP NOT CONFIRMED</b>\n\n"
            "We could no longer confirm an active eligible membership.\n\n"
            f"Your {settings.boosty_grace_days}-day grace period has started. "
            f"Direct downloads remain available until <b>{escape(_format_date(raw))}</b>.\n\n"
            "Renew your membership to keep uninterrupted access."
        )
    if event_type == "access_expired":
        return (
            "🔒 <b>BOOSTY ACCESS ENDED</b>\n\n"
            "Your grace period has expired. Direct PDF and EPUB downloads are now unavailable.\n\n"
            "Your account, comments, settings and title follows remain active."
        )
    if event_type == "access_restored":
        return (
            "✅ <b>BOOSTY ACCESS RESTORED</b>\n\n"
            "Your eligible membership has been confirmed again. Direct PDF and EPUB downloads are available."
        )
    return "Your Boosty access status has changed."


def _format_date(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value or "the displayed expiration time"
    return parsed.strftime("%d-%m-%Y %H:%M UTC")
