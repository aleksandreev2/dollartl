from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from dollartl.bot.keyboards import (
    back_home_keyboard,
    home_keyboard,
    settings_keyboard,
)
from dollartl.bot.texts import COMING_SOON, HELP, HOME, REGISTRATION_COMPLETE
from dollartl.config import Settings
from dollartl.db.models import User
from dollartl.db.session import SessionFactory
from dollartl.services.access import AccessService


def create_user_router(settings: Settings) -> Router:
    router = Router(name="user")

    @router.callback_query(F.data == f"consent:adult:{settings.adult_consent_version}")
    async def accept_adult_consent(callback: CallbackQuery, db_user: User) -> None:
        async with SessionFactory() as session:
            await AccessService(session).accept_consent(
                db_user.id, settings.adult_consent_version
            )
        await callback.answer("Rules accepted.")
        if callback.message is not None:
            await callback.message.edit_text(
                REGISTRATION_COMPLETE.format(anonymous_name=db_user.anonymous_name),
                reply_markup=home_keyboard(),
            )

    @router.message(Command("start"))
    async def start(message: Message, db_user: User) -> None:
        await message.answer(
            HOME.format(anonymous_name=db_user.anonymous_name),
            reply_markup=home_keyboard(),
        )

    @router.callback_query(F.data == "menu:home")
    async def home(callback: CallbackQuery, db_user: User) -> None:
        await callback.answer()
        if callback.message is not None:
            await callback.message.edit_text(
                HOME.format(anonymous_name=db_user.anonymous_name),
                reply_markup=home_keyboard(),
            )

    @router.callback_query(F.data == "menu:help")
    async def help_callback(callback: CallbackQuery) -> None:
        await callback.answer()
        if callback.message is not None:
            await callback.message.edit_text(HELP, reply_markup=back_home_keyboard())

    @router.message(Command("help"))
    async def help_message(message: Message) -> None:
        await message.answer(HELP, reply_markup=back_home_keyboard())

    @router.callback_query(F.data == "menu:settings")
    async def settings_callback(callback: CallbackQuery, db_user: User) -> None:
        async with SessionFactory() as session:
            enabled = await AccessService(session).get_new_title_notifications(db_user.id)
        await callback.answer()
        if callback.message is not None:
            await callback.message.edit_text(
                _settings_text(db_user, enabled),
                reply_markup=settings_keyboard(enabled),
            )

    @router.message(Command("settings"))
    async def settings_message(message: Message, db_user: User) -> None:
        async with SessionFactory() as session:
            enabled = await AccessService(session).get_new_title_notifications(db_user.id)
        await message.answer(
            _settings_text(db_user, enabled),
            reply_markup=settings_keyboard(enabled),
        )

    @router.callback_query(F.data == "settings:toggle:new_titles")
    async def toggle_new_titles(callback: CallbackQuery, db_user: User) -> None:
        async with SessionFactory() as session:
            enabled = await AccessService(session).toggle_new_title_notifications(db_user.id)
        await callback.answer("Setting updated.")
        if callback.message is not None:
            await callback.message.edit_text(
                _settings_text(db_user, enabled),
                reply_markup=settings_keyboard(enabled),
            )

    @router.callback_query(F.data.startswith("soon:"))
    async def coming_soon(callback: CallbackQuery) -> None:
        await callback.answer(COMING_SOON, show_alert=True)

    @router.message()
    async def fallback(message: Message, db_user: User) -> None:
        await message.answer(
            HOME.format(anonymous_name=db_user.anonymous_name),
            reply_markup=home_keyboard(),
        )

    return router


def _settings_text(user: User, enabled: bool) -> str:
    state = "Enabled" if enabled else "Disabled"
    return (
        "⚙️ <b>SETTINGS</b>\n\n"
        f"Public name: <b>{user.anonymous_name}</b>\n"
        f"New title announcements: <b>{state}</b>\n\n"
        "Service notifications are always enabled."
    )
