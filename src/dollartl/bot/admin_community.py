from __future__ import annotations

from uuid import UUID

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from dollartl.config import Settings
from dollartl.db.session import SessionFactory
from dollartl.services.community import CommunityService


def create_admin_community_router(settings: Settings) -> Router:
    router = Router(name="admin-community")

    def allowed(message: Message) -> bool:
        return message.from_user is not None and message.from_user.id == settings.admin_telegram_id

    @router.message(Command("comment_delete"))
    async def comment_delete(message: Message, command: CommandObject) -> None:
        if not allowed(message):
            return
        try:
            comment_id = UUID((command.args or "").strip())
        except ValueError:
            await message.answer("Использование: /comment_delete <uuid>")
            return
        async with SessionFactory() as session:
            changed = await CommunityService(session, settings).delete_comment(
                comment_id, admin_telegram_id=settings.admin_telegram_id
            )
        await message.answer("Комментарий удалён." if changed else "Комментарий не найден.")

    @router.message(Command("comment_restore"))
    async def comment_restore(message: Message, command: CommandObject) -> None:
        if not allowed(message):
            return
        try:
            comment_id = UUID((command.args or "").strip())
        except ValueError:
            await message.answer("Использование: /comment_restore <uuid>")
            return
        async with SessionFactory() as session:
            changed = await CommunityService(session, settings).restore_comment(
                comment_id, settings.admin_telegram_id
            )
        await message.answer("Комментарий восстановлен." if changed else "Изменений нет.")

    @router.message(Command("rating_status"))
    async def rating_status(message: Message, command: CommandObject) -> None:
        if not allowed(message):
            return
        parts = (command.args or "").split(maxsplit=2)
        if len(parts) < 2:
            await message.answer(
                "Использование: /rating_status <uuid> <new|reviewed|in_progress|fixed|dismissed> [заметка]"
            )
            return
        try:
            rating_id = UUID(parts[0])
            async with SessionFactory() as session:
                changed = await CommunityService(session, settings).set_rating_status(
                    rating_id,
                    status=parts[1],
                    admin_telegram_id=settings.admin_telegram_id,
                    note=parts[2] if len(parts) > 2 else None,
                )
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await message.answer("Статус оценки обновлён." if changed else "Оценка не найдена.")

    @router.message(Command("report_status"))
    async def report_status(message: Message, command: CommandObject) -> None:
        if not allowed(message):
            return
        parts = (command.args or "").split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(
                "Использование: /report_status <uuid> <open|in_progress|resolved|rejected>"
            )
            return
        try:
            report_id = UUID(parts[0])
            async with SessionFactory() as session:
                report = await CommunityService(session, settings).set_report_status(
                    report_id,
                    status=parts[1],
                    admin_telegram_id=settings.admin_telegram_id,
                )
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await message.answer("Статус жалобы обновлён." if report else "Жалоба не найдена.")

    @router.message(Command("report_reply"))
    async def report_reply(message: Message, command: CommandObject, bot: Bot) -> None:
        if not allowed(message):
            return
        raw = command.args or ""
        if "|" not in raw:
            await message.answer("Использование: /report_reply <uuid> | <ответ>")
            return
        raw_id, body = [part.strip() for part in raw.split("|", 1)]
        try:
            report_id = UUID(raw_id)
        except ValueError:
            await message.answer("Некорректный UUID.")
            return
        async with SessionFactory() as session:
            service = CommunityService(session, settings)
            report = await service.reply_report(
                report_id,
                admin_telegram_id=settings.admin_telegram_id,
                body=body,
            )
            if report is None:
                await message.answer("Жалоба не найдена.")
                return
            from dollartl.db.models import User
            user = await session.get(User, report.user_id)
        if user is not None:
            await bot.send_message(
                user.telegram_id,
                "📩 <b>REPORT UPDATE</b>\n\n"
                f"Report: <code>{report.id}</code>\n\n{body}",
            )
        await message.answer("Ответ отправлен.")

    @router.message(Command("community_stats"))
    async def community_stats(message: Message) -> None:
        if not allowed(message):
            return
        async with SessionFactory() as session:
            counts = await CommunityService(session, settings).report_counts()
        await message.answer(
            "📊 <b>COMMUNITY STATS</b>\n\n"
            + "\n".join(f"{key}: {value}" for key, value in sorted(counts.items()))
        )

    return router
