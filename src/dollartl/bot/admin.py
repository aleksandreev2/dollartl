from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from dollartl.config import Settings
from dollartl.db.session import SessionFactory
from dollartl.services.access import AccessService, BAN_REASON_TEMPLATES


def parse_duration(value: str, *, now: datetime | None = None) -> tuple[str, datetime | None]:
    normalized = value.strip().lower()
    if normalized in {"permanent", "forever", "perm"}:
        return "permanent", None
    if len(normalized) < 2 or normalized[-1] not in {"h", "d"}:
        raise ValueError("Use 6h, 1d, 7d, 30d or permanent.")
    amount = int(normalized[:-1])
    if amount <= 0:
        raise ValueError("Duration must be positive.")
    current = now or datetime.now(timezone.utc)
    delta = timedelta(hours=amount) if normalized[-1] == "h" else timedelta(days=amount)
    return "temporary", current + delta


def resolve_reason(value: str) -> tuple[str, str | None]:
    stripped = value.strip()
    if not stripped:
        raise ValueError("A public reason is required.")
    template = BAN_REASON_TEMPLATES.get(stripped.lower())
    return (template, stripped.lower()) if template else (stripped, None)


def create_admin_router(settings: Settings) -> Router:
    router = Router(name="admin")

    @router.message(Command("admin"))
    async def open_admin(message: Message) -> None:
        if message.from_user is None or message.from_user.id != settings.admin_telegram_id:
            return
        if not settings.admin_web_url:
            await message.answer("ADMIN_WEB_URL is not configured.")
            return
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Открыть административную панель", web_app=WebAppInfo(url=settings.admin_web_url))]])
        await message.answer("Административная Mini App доступна только вашему Telegram ID.", reply_markup=keyboard)

    @router.message(Command("ban"))
    async def ban_user(message: Message) -> None:
        if message.from_user is None or message.from_user.id != settings.admin_telegram_id:
            return
        parts = (message.text or "").split(maxsplit=3)
        if len(parts) < 4:
            await message.answer("Usage: /ban <telegram_id> <6h|1d|7d|30d|permanent> <template or reason>")
            return
        try:
            target_id = int(parts[1])
            ban_type, expires_at = parse_duration(parts[2])
            reason, reason_template = resolve_reason(parts[3])
        except (ValueError, TypeError) as exc:
            await message.answer(f"Invalid ban: {exc}")
            return
        async with SessionFactory() as session:
            service = AccessService(session)
            target = await service.get_user_by_telegram_id(target_id)
            if target is None:
                await message.answer("User is not registered in the bot.")
                return
            await service.create_ban(target=target, ban_type=ban_type, expires_at=expires_at, public_reason=reason, reason_template=reason_template, admin_telegram_id=settings.admin_telegram_id)
        expiry = expires_at.isoformat() if expires_at else "the end of time"
        await message.answer(f"User {target_id} blocked until {escape(expiry)}.\nReason: {escape(reason)}")

    @router.message(Command("unban"))
    async def unban_user(message: Message) -> None:
        if message.from_user is None or message.from_user.id != settings.admin_telegram_id:
            return
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 2:
            await message.answer("Usage: /unban <telegram_id> [internal note]")
            return
        try:
            target_id = int(parts[1])
        except ValueError:
            await message.answer("Telegram ID must be a number.")
            return
        note = parts[2] if len(parts) == 3 else None
        async with SessionFactory() as session:
            service = AccessService(session)
            target = await service.get_user_by_telegram_id(target_id)
            if target is None:
                await message.answer("User is not registered in the bot.")
                return
            count = await service.unban_user(target=target, admin_telegram_id=settings.admin_telegram_id, note=note)
        await message.answer(f"Active bans removed: {count}." if count else "The user has no active ban.")

    @router.message(Command("ban_templates"))
    async def ban_templates(message: Message) -> None:
        if message.from_user is None or message.from_user.id != settings.admin_telegram_id:
            return
        lines = ["Available ban reason templates:"]
        lines.extend(f"• {key}: {value}" for key, value in BAN_REASON_TEMPLATES.items())
        await message.answer("\n".join(lines))

    return router
