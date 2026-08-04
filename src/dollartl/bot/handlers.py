from __future__ import annotations

from aiogram import F, Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from dollartl.bot.catalog import send_deep_link_target
from dollartl.bot.keyboards import back_home_keyboard, home_keyboard, settings_keyboard
from dollartl.bot.texts import COMING_SOON, HELP, HOME, REGISTRATION_COMPLETE
from dollartl.config import Settings
from dollartl.db.models import User
from dollartl.db.session import SessionFactory
from dollartl.services.access import AccessService


def create_user_router(settings: Settings) -> Router:
    router = Router(name="user")

    @router.callback_query(F.data == f"consent:adult:{settings.adult_consent_version}")
    async def accept_adult_consent(
        callback: CallbackQuery, db_user: User, bot: Bot
    ) -> None:
        async with SessionFactory() as session:
            service = AccessService(session)
            await service.accept_consent(db_user.id, settings.adult_consent_version)
            pending_token = await service.pop_pending_deep_link(db_user.id)
        await callback.answer("Rules accepted.")
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                REGISTRATION_COMPLETE.format(anonymous_name=db_user.anonymous_name),
                reply_markup=home_keyboard(),
            )
        if pending_token:
            opened = await send_deep_link_target(
                bot=bot,
                chat_id=callback.from_user.id,
                token=pending_token,
                db_user=db_user,
                settings=settings,
            )
            if not opened:
                await bot.send_message(
                    callback.from_user.id,
                    "The requested title or release is no longer available.",
                    reply_markup=home_keyboard(),
                )

    @router.message(Command("start"))
    async def start(
        message: Message, db_user: User, command: CommandObject, bot: Bot
    ) -> None:
        token = (command.args or "").strip()
        if token:
            opened = await send_deep_link_target(
                bot=bot,
                chat_id=message.chat.id,
                token=token,
                db_user=db_user,
                settings=settings,
            )
            if opened:
                return
        await message.answer(
            HOME.format(anonymous_name=db_user.anonymous_name),
            reply_markup=home_keyboard(),
        )

    @router.callback_query(F.data == "menu:home")
    async def home(callback: CallbackQuery, db_user: User) -> None:
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                HOME.format(anonymous_name=db_user.anonymous_name),
                reply_markup=home_keyboard(),
            )

    @router.callback_query(F.data == "menu:help")
    async def help_callback(callback: CallbackQuery) -> None:
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(HELP, reply_markup=back_home_keyboard())

    @router.message(Command("help"))
    async def help_message(message: Message) -> None:
        await message.answer(HELP, reply_markup=back_home_keyboard())

    @router.callback_query(F.data == "menu:settings")
    async def settings_callback(callback: CallbackQuery, db_user: User) -> None:
        async with SessionFactory() as session:
            enabled = await AccessService(session).get_new_title_notifications(db_user.id)
        await callback.answer()
        if isinstance(callback.message, Message):
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
        if isinstance(callback.message, Message):
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
    access = "Enabled" if user.manual_download_access else "Boosty verification pending"
    return (
        "⚙️ <b>SETTINGS</b>\n\n"
        f"Public name: <b>{user.anonymous_name}</b>\n"
        f"Direct downloads: <b>{access}</b>\n"
        f"New title announcements: <b>{state}</b>\n\n"
        "Service notifications are always enabled."
    )
