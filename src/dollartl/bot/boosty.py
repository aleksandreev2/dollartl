from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from dollartl.bot.boosty_keyboards import boosty_code_keyboard, boosty_status_keyboard
from dollartl.bot.boosty_texts import render_code, render_status
from dollartl.config import Settings
from dollartl.db.models import User
from dollartl.db.session import SessionFactory
from dollartl.services.boosty import BoostyService


async def _status_payload(
    user: User, settings: Settings
) -> tuple[str, InlineKeyboardMarkup]:
    async with SessionFactory() as session:
        status = await BoostyService(session, settings).get_status(user.id)
    return render_status(status, settings.app_timezone), boosty_status_keyboard(status.status, settings)


def create_boosty_router(settings: Settings) -> Router:
    router = Router(name="boosty")

    @router.message(Command("boosty"))
    async def boosty_command(message: Message, db_user: User) -> None:
        text, keyboard = await _status_payload(db_user, settings)
        await message.answer(text, reply_markup=keyboard)

    @router.callback_query(F.data.in_({"soon:boosty", "boosty:status"}))
    async def boosty_status(callback: CallbackQuery, db_user: User) -> None:
        text, keyboard = await _status_payload(db_user, settings)
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(text, reply_markup=keyboard)

    @router.callback_query(F.data == "boosty:verify")
    async def boosty_verify(callback: CallbackQuery, db_user: User) -> None:
        if not settings.boosty_enabled:
            await callback.answer("Boosty verification is not configured yet.", show_alert=True)
            return
        async with SessionFactory() as session:
            code = await BoostyService(session, settings).create_verification_code(db_user.id)
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                render_code(code.code, code.expires_at, settings.app_timezone),
                reply_markup=boosty_code_keyboard(settings),
            )

    @router.callback_query(F.data == "boosty:check")
    async def boosty_check(callback: CallbackQuery, db_user: User) -> None:
        async with SessionFactory() as session:
            service = BoostyService(session, settings)
            requested = await service.request_immediate_check(db_user.id)
            status = await service.get_status(db_user.id)
        if requested:
            await callback.answer("Automatic check requested. Refresh again shortly.")
        else:
            await callback.answer("Current Boosty status loaded.")
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                render_status(status, settings.app_timezone),
                reply_markup=boosty_status_keyboard(status.status, settings),
            )

    return router
