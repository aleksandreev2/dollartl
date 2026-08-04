from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert

from dollartl.config import Settings
from dollartl.db.admin_models import Broadcast, BroadcastRecipient
from dollartl.db.boosty_models import BoostyLink
from dollartl.db.models import Ban, User, UserTitleFollow
from dollartl.db.session import SessionFactory
from dollartl.storage import S3Storage


def _active_ban(now: datetime):
    return exists(select(Ban.id).where(Ban.user_id == User.id, Ban.is_active.is_(True), or_(Ban.ban_type == "permanent", Ban.expires_at.is_(None), Ban.expires_at > now)))


async def _claim() -> UUID | None:
    now = datetime.now(timezone.utc)
    async with SessionFactory() as session:
        item = (await session.execute(select(Broadcast).where(Broadcast.status.in_(["scheduled", "processing"]), or_(Broadcast.scheduled_at.is_(None), Broadcast.scheduled_at <= now)).order_by(Broadcast.scheduled_at.asc().nullsfirst(), Broadcast.created_at.asc()).with_for_update(skip_locked=True).limit(1))).scalar_one_or_none()
        if item is None:
            return None
        if item.status == "scheduled":
            item.status = "processing"
            item.started_at = now
        await session.commit()
        return item.id


async def _audience(item: Broadcast) -> list[UUID]:
    now = datetime.now(timezone.utc)
    async with SessionFactory() as session:
        statement = select(User.id).where(User.is_active.is_(True), ~_active_ban(now))
        if item.audience_type == "active_vip":
            statement = statement.join(BoostyLink, BoostyLink.user_id == User.id).where(BoostyLink.status == "active_vip")
        elif item.audience_type == "vip_grace":
            statement = statement.join(BoostyLink, BoostyLink.user_id == User.id).where(or_(BoostyLink.status == "active_vip", and_(BoostyLink.status == "grace_period", BoostyLink.grace_ends_at > now)))
        elif item.audience_type == "standard":
            vip = exists(select(BoostyLink.id).where(BoostyLink.user_id == User.id, or_(BoostyLink.status == "active_vip", and_(BoostyLink.status == "grace_period", BoostyLink.grace_ends_at > now))))
            statement = statement.where(~vip)
        elif item.audience_type == "title_followers":
            if item.title_id is None:
                return []
            statement = statement.join(UserTitleFollow, UserTitleFollow.user_id == User.id).where(UserTitleFollow.title_id == item.title_id)
        elif item.audience_type == "selected":
            selected: list[UUID] = []
            for raw in item.selected_user_ids or []:
                try:
                    selected.append(UUID(str(raw)))
                except ValueError:
                    continue
            if not selected:
                return []
            statement = statement.where(User.id.in_(selected))
        return list((await session.execute(statement.distinct())).scalars())


async def _ensure_recipients(broadcast_id: UUID) -> None:
    async with SessionFactory() as session:
        item = await session.get(Broadcast, broadcast_id)
        if item is None or item.status != "processing":
            return
        existing = int((await session.execute(select(func.count(BroadcastRecipient.id)).where(BroadcastRecipient.broadcast_id == item.id))).scalar_one())
        if existing:
            return
        session.expunge(item)
    user_ids = await _audience(item)
    async with SessionFactory() as session:
        for user_id in user_ids:
            await session.execute(insert(BroadcastRecipient).values(broadcast_id=broadcast_id, user_id=user_id, status="pending").on_conflict_do_nothing(index_elements=[BroadcastRecipient.broadcast_id, BroadcastRecipient.user_id]))
        persisted = await session.get(Broadcast, broadcast_id)
        if persisted is not None:
            persisted.total_count = len(user_ids)
        await session.commit()


async def _batch(broadcast_id: UUID, limit: int) -> list[tuple[BroadcastRecipient, User]]:
    async with SessionFactory() as session:
        rows = (await session.execute(select(BroadcastRecipient, User).join(User, User.id == BroadcastRecipient.user_id).where(BroadcastRecipient.broadcast_id == broadcast_id, BroadcastRecipient.status.in_(["pending", "failed"]), BroadcastRecipient.attempts < 5).order_by(BroadcastRecipient.created_at.asc()).with_for_update(skip_locked=True).limit(limit))).all()
        for recipient, _ in rows:
            recipient.attempts += 1
        await session.commit()
        for recipient, user in rows:
            session.expunge(recipient)
            session.expunge(user)
        return list(rows)


async def _mark(recipient_id: UUID, state: str, error: str | None = None, message_id: int | None = None) -> None:
    async with SessionFactory() as session:
        recipient = await session.get(BroadcastRecipient, recipient_id)
        if recipient is None:
            return
        recipient.status = state
        recipient.last_error = error[:2000] if error else None
        recipient.telegram_message_id = message_id
        recipient.sent_at = datetime.now(timezone.utc) if state == "sent" else None
        await session.commit()


async def _send(bot: Bot, item: Broadcast, recipient: BroadcastRecipient, user: User, settings: Settings) -> None:
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=item.button_text, url=item.button_url)]]) if item.button_text and item.button_url else None
    temp_path: Path | None = None
    try:
        if item.photo_object_key:
            temp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            temp.close()
            temp_path = Path(temp.name)
            await asyncio.to_thread(S3Storage(settings).download_file, item.photo_object_key, temp_path)
            sent = await bot.send_photo(user.telegram_id, FSInputFile(temp_path), caption=item.text, reply_markup=markup)
        else:
            sent = await bot.send_message(user.telegram_id, item.text, reply_markup=markup)
    except TelegramRetryAfter as exc:
        await asyncio.sleep(min(float(exc.retry_after), 30.0))
        await _mark(recipient.id, "failed", f"retry_after:{exc.retry_after}")
    except TelegramForbiddenError as exc:
        await _mark(recipient.id, "skipped", f"{type(exc).__name__}: {exc}")
    except Exception as exc:
        await _mark(recipient.id, "failed", f"{type(exc).__name__}: {exc}")
    else:
        await _mark(recipient.id, "sent", message_id=sent.message_id)
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)


async def _finalize(broadcast_id: UUID) -> None:
    async with SessionFactory() as session:
        item = await session.get(Broadcast, broadcast_id)
        if item is None:
            return
        counts = dict((await session.execute(select(BroadcastRecipient.status, func.count(BroadcastRecipient.id)).where(BroadcastRecipient.broadcast_id == broadcast_id).group_by(BroadcastRecipient.status))).all())
        item.sent_count = int(counts.get("sent", 0))
        item.failed_count = int(counts.get("failed", 0))
        item.skipped_count = int(counts.get("skipped", 0))
        retriable = int((await session.execute(select(func.count(BroadcastRecipient.id)).where(BroadcastRecipient.broadcast_id == broadcast_id, BroadcastRecipient.status.in_(["pending", "failed"]), BroadcastRecipient.attempts < 5))).scalar_one())
        if retriable == 0:
            item.status = "completed" if item.sent_count or item.total_count == 0 else "failed"
            item.completed_at = datetime.now(timezone.utc)
        await session.commit()


async def process_next_broadcast(bot: Bot, settings: Settings) -> bool:
    broadcast_id = await _claim()
    if broadcast_id is None:
        return False
    await _ensure_recipients(broadcast_id)
    async with SessionFactory() as session:
        item = await session.get(Broadcast, broadcast_id)
        if item is None or item.status != "processing":
            return True
        session.expunge(item)
    for recipient, user in await _batch(broadcast_id, settings.broadcast_batch_size):
        await _send(bot, item, recipient, user, settings)
        await asyncio.sleep(settings.broadcast_send_delay_seconds)
    await _finalize(broadcast_id)
    return True
