from __future__ import annotations

import logging
from html import escape
from datetime import datetime, timezone
from uuid import UUID

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.dialects.postgresql import insert

from dollartl.config import Settings
from dollartl.db.models import (
    Ban,
    ChannelPublication,
    NotificationPreference,
    OutboxDelivery,
    OutboxEvent,
    Release,
    Title,
    User,
    UserConsent,
    UserTitleFollow,
)
from dollartl.db.session import SessionFactory
from dollartl.services.access import ADULT_CONSENT_TYPE

logger = logging.getLogger(__name__)


def deep_link_url(settings: Settings, token: str, bot_username: str) -> str:
    username = settings.normalized_bot_username or bot_username.lstrip("@")
    return f"https://t.me/{username}?start={token}"


def _active_ban_exists(now: datetime) -> ColumnElement[bool]:
    return exists(
        select(Ban.id).where(
            Ban.user_id == User.id,
            Ban.is_active.is_(True),
            or_(Ban.ban_type == "permanent", Ban.expires_at.is_(None), Ban.expires_at > now),
        )
    )


async def _load_event() -> OutboxEvent | None:
    async with SessionFactory() as session:
        event = (
            await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.published.is_(False))
                .order_by(OutboxEvent.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(1)
            )
        ).scalar_one_or_none()
        if event is None:
            return None
        session.expunge(event)
        return event


async def _mark_event_published(event_id: UUID) -> None:
    async with SessionFactory() as session:
        event = await session.get(OutboxEvent, event_id)
        if event is not None:
            event.published = True
            event.published_at = datetime.now(timezone.utc)
            await session.commit()


async def _publish_channel(
    *, bot: Bot, settings: Settings, event: OutboxEvent, bot_username: str
) -> bool:
    if not settings.channel_posts_enabled:
        return True
    target_type = event.aggregate_type
    target_id = event.aggregate_id
    async with SessionFactory() as session:
        existing = (
            await session.execute(
                select(ChannelPublication).where(
                    ChannelPublication.target_type == target_type,
                    ChannelPublication.target_id == target_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None and existing.status == "sent":
            return True

        token = str(event.payload.get("deep_link_token", ""))
        open_button = InlineKeyboardButton(
            text="📚 Open in Bot",
            url=deep_link_url(settings, token, bot_username),
        )
        buttons = [open_button]
        if target_type == "title":
            title = await session.get(Title, UUID(target_id))
            if title is None:
                logger.error("outbox_title_missing", extra={"target_id": target_id})
                return False
            text = (
                f"🆕 <b>NEW TITLE</b>\n\n"
                f"<b>{escape(title.english_title)}</b>\n\n"
                f"Original title: {escape(title.original_title)}\n"
                f"Available chapters: {f'1–{title.latest_chapter}' if title.latest_chapter else 'Coming soon'}\n\n"
                "PDF and EPUB are available through Dollar TL."
            )
            if title.boosty_url:
                buttons.append(InlineKeyboardButton(text="🌐 View on Boosty", url=title.boosty_url))
        elif target_type == "release":
            release = await session.get(Release, UUID(target_id))
            if release is None:
                logger.error("outbox_release_missing", extra={"target_id": target_id})
                return False
            title = await session.get(Title, release.title_id)
            if title is None:
                return False
            text = (
                f"📖 <b>NEW RELEASE</b>\n\n"
                f"<b>{escape(title.english_title)}</b>\n"
                f"{escape(release.chapter_label)}\n\n"
                "PDF and EPUB are now available."
            )
            boosty_url = release.boosty_url or title.boosty_url
            if boosty_url:
                buttons.append(InlineKeyboardButton(text="🌐 View on Boosty", url=boosty_url))
        else:
            return True

        publication = existing or ChannelPublication(
            target_type=target_type,
            target_id=target_id,
            telegram_chat_id=settings.telegram_channel_username,
            status="pending",
        )
        if existing is None:
            session.add(publication)
        try:
            sent = await bot.send_message(
                chat_id=settings.telegram_channel_username,
                text=text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[buttons]),
                protect_content=False,
            )
        except Exception as exc:
            publication.status = "failed"
            publication.error = f"{type(exc).__name__}: {exc}"[:2000]
            await session.commit()
            logger.exception("channel_publication_failed")
            return False
        publication.status = "sent"
        publication.telegram_message_id = sent.message_id
        publication.error = None
        await session.commit()
        return True


async def _recipient_ids(event: OutboxEvent, settings: Settings) -> list[UUID]:
    now = datetime.now(timezone.utc)
    async with SessionFactory() as session:
        statement = (
            select(User.id)
            .join(
                UserConsent,
                and_(
                    UserConsent.user_id == User.id,
                    UserConsent.consent_type == ADULT_CONSENT_TYPE,
                    UserConsent.version == settings.adult_consent_version,
                ),
            )
            .where(User.is_active.is_(True), ~_active_ban_exists(now))
        )
        if event.topic == "title.published":
            statement = statement.join(
                NotificationPreference,
                NotificationPreference.user_id == User.id,
            ).where(NotificationPreference.new_title_announcements.is_(True))
        elif event.topic == "release.published":
            title_id = UUID(str(event.payload["title_id"]))
            statement = statement.join(
                UserTitleFollow, UserTitleFollow.user_id == User.id
            ).where(UserTitleFollow.title_id == title_id)
        else:
            return []
        return list((await session.execute(statement.distinct())).scalars())


async def _notification_payload(
    event: OutboxEvent, settings: Settings, bot_username: str
) -> tuple[str, InlineKeyboardMarkup] | None:
    token = str(event.payload.get("deep_link_token", ""))
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📚 Open Title" if event.topic == "title.published" else "📦 Open Release",
                    url=deep_link_url(settings, token, bot_username),
                )
            ]
        ]
    )
    async with SessionFactory() as session:
        if event.topic == "title.published":
            title = await session.get(Title, UUID(event.aggregate_id))
            if title is None:
                return None
            text = (
                f"🆕 <b>NEW TITLE</b>\n\n"
                f"<b>{escape(title.english_title)}</b>\n\n"
                f"Original title: {escape(title.original_title)}\n"
                f"Formats: PDF + EPUB"
            )
            return text, keyboard
        if event.topic == "release.published":
            release = await session.get(Release, UUID(event.aggregate_id))
            if release is None:
                return None
            title = await session.get(Title, release.title_id)
            if title is None:
                return None
            text = (
                f"📖 <b>NEW CHAPTERS AVAILABLE</b>\n\n"
                f"<b>{escape(title.english_title)}</b>\n\n"
                f"New release: {escape(release.chapter_label)}\n"
                "PDF and EPUB are now available."
            )
            return text, keyboard
    return None


async def _deliver_to_user(
    *, bot: Bot, event: OutboxEvent, user_id: UUID, text: str, keyboard: InlineKeyboardMarkup
) -> bool:
    async with SessionFactory() as session:
        delivery = (
            await session.execute(
                select(OutboxDelivery).where(
                    OutboxDelivery.event_id == event.id,
                    OutboxDelivery.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if delivery is not None and delivery.status in {"sent", "skipped"}:
            return True
        user = await session.get(User, user_id)
        if user is None:
            return True
        if delivery is None:
            await session.execute(
                insert(OutboxDelivery)
                .values(event_id=event.id, user_id=user_id, status="pending")
                .on_conflict_do_nothing(
                    index_elements=[OutboxDelivery.event_id, OutboxDelivery.user_id]
                )
            )
            await session.commit()
            delivery = (
                await session.execute(
                    select(OutboxDelivery).where(
                        OutboxDelivery.event_id == event.id,
                        OutboxDelivery.user_id == user_id,
                    )
                )
            ).scalar_one()
        try:
            sent = await bot.send_message(
                chat_id=user.telegram_id,
                text=text,
                reply_markup=keyboard,
            )
        except TelegramForbiddenError as exc:
            delivery.status = "skipped"
            delivery.error = f"{type(exc).__name__}: {exc}"[:2000]
            await session.commit()
            return True
        except Exception as exc:
            delivery.status = "failed"
            delivery.error = f"{type(exc).__name__}: {exc}"[:2000]
            await session.commit()
            return False
        delivery.status = "sent"
        delivery.telegram_message_id = sent.message_id
        delivery.error = None
        await session.commit()
        return True


async def process_next_publication(bot: Bot, settings: Settings) -> bool:
    event = await _load_event()
    if event is None:
        return False
    me = await bot.get_me()
    bot_username = me.username or settings.normalized_bot_username
    if not bot_username:
        logger.error("bot_username_unavailable")
        return False

    channel_ok = await _publish_channel(
        bot=bot, settings=settings, event=event, bot_username=bot_username
    )
    payload = await _notification_payload(event, settings, bot_username)
    if payload is None:
        return False
    text, keyboard = payload
    users_ok = True
    for user_id in await _recipient_ids(event, settings):
        delivered = await _deliver_to_user(
            bot=bot,
            event=event,
            user_id=user_id,
            text=text,
            keyboard=keyboard,
        )
        users_ok = users_ok and delivered
    if channel_ok and users_ok:
        await _mark_event_published(event.id)
    return True
