from __future__ import annotations

from html import escape
from uuid import UUID

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from dollartl.config import Settings
from dollartl.db.models import User
from dollartl.db.session import SessionFactory
from dollartl.services.suggestions import PUBLIC_STATUS, SuggestionService


def _uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


def _owner(message: Message, settings: Settings) -> bool:
    return bool(message.from_user and message.from_user.id == settings.admin_telegram_id)


def create_admin_suggestion_router(settings: Settings) -> Router:
    router = Router(name="admin_suggestions")

    @router.message(Command("suggestion_list"))
    async def list_suggestions(message: Message, command: CommandObject) -> None:
        if not _owner(message, settings):
            return
        status = (command.args or "under_review").strip().casefold()
        if status not in {"under_review", "accepted", "translated", "rejected", "all"}:
            await message.answer(
                "Usage: /suggestion_list [under_review|accepted|translated|rejected|all]"
            )
            return
        async with SessionFactory() as session:
            items = await SuggestionService(session, settings).list_admin(status)
        if not items:
            await message.answer("Заявок с таким статусом нет.")
            return
        lines = [f"💡 <b>ЗАЯВКИ: {status}</b>"]
        for item in items:
            flag = " ⚠️ duplicate" if item.duplicate_review_required else ""
            lines.append(
                f"\n<code>{item.id}</code>\n"
                f"{escape(item.original_title or 'Untitled')} — "
                f"{PUBLIC_STATUS.get(item.status, item.status)}{flag}"
            )
        await message.answer("\n".join(lines))

    @router.message(Command("suggestion_show"))
    async def show_suggestion(message: Message, command: CommandObject) -> None:
        if not _owner(message, settings):
            return
        suggestion_id = _uuid((command.args or "").strip())
        if suggestion_id is None:
            await message.answer("Usage: /suggestion_show <uuid>")
            return
        async with SessionFactory() as session:
            service = SuggestionService(session, settings)
            suggestion = await service.get(suggestion_id)
            payload = await service.review(suggestion_id) if suggestion else None
            owner = await session.get(User, suggestion.user_id) if suggestion else None
        if suggestion is None:
            await message.answer("Заявка не найдена.")
            return
        await message.answer(
            "💡 <b>ЗАЯВКА</b>\n\n"
            f"ID: <code>{suggestion.id}</code>\n"
            f"Пользователь: {owner.telegram_id if owner else '?'}\n"
            f"Название: {escape(suggestion.original_title or 'Untitled')}\n"
            f"Язык: {escape(suggestion.detected_language or 'Unknown')}\n"
            f"Главы: {suggestion.chapter_count or '?'}\n"
            f"Scope: {suggestion.requested_chapter_start}–{suggestion.requested_chapter_end or '?'}\n"
            f"Статус: {PUBLIC_STATUS.get(suggestion.status, suggestion.status)}\n"
            f"VIP snapshot: {'yes' if suggestion.vip_snapshot else 'no'}\n"
            f"Duplicate review: {'required' if suggestion.duplicate_review_required else 'no'}\n"
            f"Public reason: {escape(suggestion.public_reason or '-')}\n"
            f"Internal note: {escape(suggestion.internal_note or '-')}\n"
            f"Sources: {len(payload.sources) if payload else 0}\n"
            f"Files: {', '.join(item.file_kind for item in payload.files) if payload and payload.files else 'none'}"
        )

    @router.message(Command("suggestion_status"))
    async def change_status(message: Message, command: CommandObject, bot: Bot) -> None:
        if not _owner(message, settings):
            return
        parts = [part.strip() for part in (command.args or "").split("|")]
        header = parts[0].split(maxsplit=2) if parts and parts[0] else []
        if len(header) < 2:
            await message.answer(
                "Usage: /suggestion_status <uuid> <accepted|rejected|translated> "
                "[linked_title_uuid] | public reason | internal note"
            )
            return
        suggestion_id = _uuid(header[0])
        new_status = header[1].casefold()
        linked_title_id = _uuid(header[2]) if len(header) > 2 else None
        public_reason = parts[1] if len(parts) > 1 else None
        internal_note = parts[2] if len(parts) > 2 else None
        if suggestion_id is None:
            await message.answer("Invalid suggestion UUID.")
            return
        async with SessionFactory() as session:
            service = SuggestionService(session, settings)
            suggestion = await service.get(suggestion_id)
            if suggestion is None:
                await message.answer("Заявка не найдена.")
                return
            owner = await session.get(User, suggestion.user_id)
            try:
                await service.change_status(
                    suggestion=suggestion,
                    new_status=new_status,
                    admin_telegram_id=settings.admin_telegram_id,
                    public_reason=public_reason,
                    internal_note=internal_note,
                    linked_title_id=linked_title_id,
                )
            except ValueError as exc:
                await message.answer(str(exc))
                return
        await message.answer("Статус заявки обновлён.")
        if owner is not None:
            reason = f"\n\nReason:\n{escape(public_reason)}" if public_reason else ""
            await bot.send_message(
                owner.telegram_id,
                "💡 <b>SUGGESTION STATUS UPDATED</b>\n\n"
                f"{escape(suggestion.original_title or 'Untitled')}\n"
                f"Status: <b>{PUBLIC_STATUS.get(new_status, new_status)}</b>"
                f"{reason}",
            )

    @router.message(Command("suggestion_restore_slot"))
    async def restore_slot(message: Message, command: CommandObject) -> None:
        if not _owner(message, settings):
            return
        parts = (command.args or "").split(maxsplit=1)
        suggestion_id = _uuid(parts[0]) if parts else None
        if suggestion_id is None:
            await message.answer("Usage: /suggestion_restore_slot <uuid> [reason]")
            return
        reason = parts[1] if len(parts) > 1 else "Duplicate or administrative correction"
        async with SessionFactory() as session:
            restored = await SuggestionService(session, settings).restore_quota_slot(
                suggestion_id,
                settings.admin_telegram_id,
                reason,
            )
        await message.answer(
            "Слот восстановлен." if restored else "Активное списание квоты не найдено."
        )

    return router
