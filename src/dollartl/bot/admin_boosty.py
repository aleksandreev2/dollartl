from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from dollartl.config import Settings
from dollartl.db.session import SessionFactory
from dollartl.services.access import AccessService
from dollartl.services.boosty import BoostyService


def create_admin_boosty_router(settings: Settings) -> Router:
    router = Router(name="admin_boosty")

    @router.message(Command("boosty_link"))
    async def manual_link(message: Message) -> None:
        if message.from_user is None or message.from_user.id != settings.admin_telegram_id:
            return
        parts = (message.text or "").split(maxsplit=4)
        if len(parts) < 5:
            await message.answer(
                "Использование: /boosty_link <telegram_id> <boosty_user_id> <username|-> <active|expired>"
            )
            return
        try:
            telegram_id = int(parts[1])
        except ValueError:
            await message.answer("Некорректный Telegram ID.")
            return
        active = parts[4].lower() == "active"
        if parts[4].lower() not in {"active", "expired"}:
            await message.answer("Статус должен быть active или expired.")
            return
        async with SessionFactory() as session:
            user = await AccessService(session).get_user_by_telegram_id(telegram_id)
            if user is None:
                await message.answer("Пользователь ещё не зарегистрирован в боте.")
                return
            try:
                link = await BoostyService(session, settings).manual_link(
                    user=user,
                    boosty_user_id=parts[2],
                    boosty_username=None if parts[3] == "-" else parts[3],
                    active=active,
                    admin_telegram_id=settings.admin_telegram_id,
                )
            except ValueError as exc:
                await message.answer(str(exc))
                return
        await message.answer(f"Boosty привязка сохранена. Статус: {link.status}.")

    @router.message(Command("boosty_unlink"))
    async def unlink(message: Message) -> None:
        if message.from_user is None or message.from_user.id != settings.admin_telegram_id:
            return
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) != 2:
            await message.answer("Использование: /boosty_unlink <telegram_id>")
            return
        try:
            telegram_id = int(parts[1])
        except ValueError:
            await message.answer("Некорректный Telegram ID.")
            return
        async with SessionFactory() as session:
            user = await AccessService(session).get_user_by_telegram_id(telegram_id)
            if user is None:
                await message.answer("Пользователь не найден.")
                return
            removed = await BoostyService(session, settings).unlink(
                user=user, admin_telegram_id=settings.admin_telegram_id
            )
        await message.answer("Привязка удалена." if removed else "Привязки не было.")

    @router.message(Command("boosty_status"))
    async def status(message: Message) -> None:
        if message.from_user is None or message.from_user.id != settings.admin_telegram_id:
            return
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) != 2:
            await message.answer("Использование: /boosty_status <telegram_id>")
            return
        try:
            telegram_id = int(parts[1])
        except ValueError:
            await message.answer("Некорректный Telegram ID.")
            return
        async with SessionFactory() as session:
            user = await AccessService(session).get_user_by_telegram_id(telegram_id)
            if user is None:
                await message.answer("Пользователь не найден.")
                return
            snapshot = await BoostyService(session, settings).get_status(user.id)
        await message.answer(
            "Boosty status\n"
            f"Telegram ID: {telegram_id}\n"
            f"Status: {snapshot.status}\n"
            f"Boosty: {snapshot.boosty_username or '-'}\n"
            f"Grace ends: {snapshot.grace_ends_at or '-'}\n"
            f"Last error: {snapshot.last_error_message or '-'}"
        )

    return router
