from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, TelegramObject, Update
from aiogram.types import User as TelegramUser

from dollartl.bot.keyboards import adult_consent_keyboard
from dollartl.bot.texts import ADULT_NOTICE, render_permanent_ban, render_temporary_ban
from dollartl.config import Settings
from dollartl.db.session import SessionFactory
from dollartl.services.access import AccessService


Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


def extract_user(update: Update) -> TelegramUser | None:
    inner = update.event
    candidate = getattr(inner, "from_user", None)
    return candidate if isinstance(candidate, TelegramUser) else None


def is_current_consent_callback(update: Update, version: int) -> bool:
    inner = update.event
    return isinstance(inner, CallbackQuery) and inner.data == f"consent:adult:{version}"


class AccessMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __call__(
        self,
        handler: Handler,
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)

        telegram_user = extract_user(event)
        if telegram_user is None:
            return await handler(event, data)

        async with SessionFactory() as session:
            service = AccessService(session)
            user = await service.ensure_user(telegram_user)
            data["db_user"] = user

            if telegram_user.id != self.settings.admin_telegram_id:
                decision = await service.resolve_ban(
                    user.id,
                    notice_interval=timedelta(
                        hours=self.settings.ban_notice_interval_hours
                    ),
                )
                if decision.blocked:
                    await self._handle_blocked(event, data["bot"], decision)
                    return None

            has_consent = await service.has_consent(
                user.id, self.settings.adult_consent_version
            )
            if not has_consent and not is_current_consent_callback(
                event, self.settings.adult_consent_version
            ):
                await self._show_consent(event, data["bot"], telegram_user.id)
                return None

        return await handler(event, data)

    async def _show_consent(self, update: Update, bot: Bot, telegram_id: int) -> None:
        inner = update.event
        if isinstance(inner, CallbackQuery):
            await inner.answer()
        await bot.send_message(
            chat_id=telegram_id,
            text=ADULT_NOTICE,
            reply_markup=adult_consent_keyboard(
                self.settings.adult_consent_version
            ),
        )

    async def _handle_blocked(
        self, update: Update, bot: Bot, decision: Any
    ) -> None:
        inner = update.event
        if isinstance(inner, CallbackQuery):
            await inner.answer()
        if not decision.should_notify:
            return
        reason = decision.public_reason or "Account access has been restricted."
        if decision.ban_type == "permanent":
            text = render_permanent_ban(reason=reason)
        elif decision.expires_at is not None:
            text = render_temporary_ban(
                expires_at=decision.expires_at,
                reason=reason,
                timezone_name=self.settings.app_timezone,
            )
        else:
            text = render_permanent_ban(reason=reason)
        telegram_user = extract_user(update)
        if telegram_user is not None:
            await bot.send_message(chat_id=telegram_user.id, text=text)
