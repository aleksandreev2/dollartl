from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from dollartl.bot.catalog import send_deep_link_target
from dollartl.bot.keyboards import (
    back_home_keyboard,
    home_keyboard,
    persistent_navigation_keyboard,
    settings_keyboard,
)
from dollartl.bot.texts import COMING_SOON, HELP, REGISTRATION_COMPLETE
from dollartl.config import Settings
from dollartl.db.models import User
from dollartl.db.session import SessionFactory
from dollartl.services.access import AccessService
from dollartl.services.boosty import BoostyService, BoostyStatus


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
        await bot.send_message(
            callback.from_user.id,
            "Quick navigation is pinned below. Use <code>/cancel</code> at any time.",
            reply_markup=persistent_navigation_keyboard(),
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
        await message.answer(
            "Quick navigation is pinned below.",
            reply_markup=persistent_navigation_keyboard(),
        )
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
            await home_text(db_user, settings),
            reply_markup=home_keyboard(),
        )

    @router.callback_query(F.data == "menu:home")
    async def home(callback: CallbackQuery, db_user: User) -> None:
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                await home_text(db_user, settings),
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
        enabled, boosty_status = await _settings_snapshot(db_user, settings)
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                _settings_text(db_user, enabled, boosty_status, settings),
                reply_markup=settings_keyboard(enabled),
            )

    @router.message(Command("settings"))
    async def settings_message(message: Message, db_user: User) -> None:
        enabled, boosty_status = await _settings_snapshot(db_user, settings)
        await message.answer(
            _settings_text(db_user, enabled, boosty_status, settings),
            reply_markup=settings_keyboard(enabled),
        )

    @router.callback_query(F.data == "settings:toggle:new_titles")
    async def toggle_new_titles(callback: CallbackQuery, db_user: User) -> None:
        async with SessionFactory() as session:
            enabled = await AccessService(session).toggle_new_title_notifications(db_user.id)
            boosty_status = await BoostyService(session, settings).get_status(db_user.id)
        await callback.answer("Setting updated.")
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                _settings_text(db_user, enabled, boosty_status, settings),
                reply_markup=settings_keyboard(enabled),
            )

    @router.callback_query(F.data.startswith("soon:"))
    async def coming_soon(callback: CallbackQuery) -> None:
        await callback.answer(COMING_SOON, show_alert=True)

    @router.message()
    async def fallback(message: Message, db_user: User) -> None:
        await message.answer(
            await home_text(db_user, settings),
            reply_markup=home_keyboard(),
        )

    return router


async def home_text(user: User, settings: Settings) -> str:
    async with SessionFactory() as session:
        status = await BoostyService(session, settings).get_status(user.id)
    access = _access_label(user, status, settings)
    account = "[VIP]" if status.has_download_access else "Standard"
    return (
        "📚 <b>DOLLAR TL</b>\n\n"
        f"Account: <b>{user.anonymous_name}</b>\n"
        f"Account level: <b>{account}</b>\n"
        f"Boosty access: <b>{access}</b>\n\n"
        "Browse translated titles, follow new chapter packages and open your library."
    )


async def _settings_snapshot(
    user: User, settings: Settings
) -> tuple[bool, BoostyStatus]:
    async with SessionFactory() as session:
        enabled = await AccessService(session).get_new_title_notifications(user.id)
        boosty_status = await BoostyService(session, settings).get_status(user.id)
    return enabled, boosty_status


def _settings_text(
    user: User,
    enabled: bool,
    boosty_status: BoostyStatus,
    settings: Settings,
) -> str:
    notification_state = "Enabled" if enabled else "Disabled"
    access = _access_label(user, boosty_status, settings)
    return (
        "⚙️ <b>SETTINGS</b>\n\n"
        f"Public name: <b>{user.anonymous_name}</b>\n"
        f"Direct downloads: <b>{access}</b>\n"
        f"New title announcements: <b>{notification_state}</b>\n\n"
        "Service notifications are always enabled."
    )


def _access_label(user: User, status: BoostyStatus, settings: Settings) -> str:
    if user.telegram_id == settings.admin_telegram_id or user.manual_download_access:
        return "Enabled"
    if status.status == "active_vip":
        return "Active [VIP]"
    if status.status == "grace_period" and status.has_download_access:
        return "Grace period [VIP]"
    if status.status == "verification_error":
        return "Verification temporarily unavailable"
    if status.status == "expired":
        return "Inactive"
    return "Not connected"
