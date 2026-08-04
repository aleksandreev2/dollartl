from __future__ import annotations

from html import escape
from uuid import UUID

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from dollartl.bot.community_keyboards import (
    RATING_CATEGORY_LABELS,
    comments_keyboard,
    my_comments_keyboard,
    nickname_keyboard,
    rating_categories_keyboard,
    rating_stars_keyboard,
    report_categories_keyboard,
)
from dollartl.config import Settings
from dollartl.db.models import User
from dollartl.db.session import SessionFactory
from dollartl.services.community import CommunityService


class CommunityStates(StatesGroup):
    nickname = State()
    comment_body = State()
    rating_feedback = State()
    report_body = State()


def _uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


def create_community_router(settings: Settings) -> Router:
    router = Router(name="community")

    @router.callback_query(F.data == "community:thanks")
    async def record_thanks(callback: CallbackQuery, db_user: User) -> None:
        async with SessionFactory() as session:
            created = await CommunityService(session, settings).record_download_thanks(
                db_user.id
            )
        await callback.answer(
            "Thank you. Download buttons are now available."
            if created
            else "Thank you was already recorded.",
            show_alert=True,
        )

    @router.callback_query(F.data == "community:nickname")
    async def nickname_start(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(CommunityStates.nickname)
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "👤 <b>DISPLAY NAME</b>\n\n"
                "Send a nickname using 3–24 characters.\n"
                "Racist slurs and advertising links are not allowed.",
                reply_markup=nickname_keyboard(),
            )

    @router.callback_query(F.data == "community:nickname:anonymous")
    async def nickname_anonymous(
        callback: CallbackQuery, db_user: User, state: FSMContext
    ) -> None:
        async with SessionFactory() as session:
            await CommunityService(session, settings).set_display_name(db_user.id, None)
        await state.clear()
        await callback.answer("Anonymous name restored.", show_alert=True)

    @router.message(CommunityStates.nickname)
    async def nickname_save(message: Message, db_user: User, state: FSMContext) -> None:
        value = (message.text or "").strip()
        try:
            async with SessionFactory() as session:
                saved = await CommunityService(session, settings).set_display_name(
                    db_user.id, value
                )
        except (PermissionError, ValueError) as exc:
            await message.answer(str(exc))
            return
        await state.clear()
        await message.answer(
            f"✅ <b>DISPLAY NAME UPDATED</b>\n\nYour comments will now appear as:\n\n<b>{escape(saved)}</b>"
        )

    @router.callback_query(F.data.startswith("cm:ls:"))
    async def comments_page(callback: CallbackQuery) -> None:
        parts = (callback.data or "").split(":")
        if len(parts) != 5:
            await callback.answer("Invalid comment page.", show_alert=True)
            return
        target_short, target_raw, page_raw = parts[2], parts[3], parts[4]
        target_type = "title" if target_short == "t" else "release" if target_short == "r" else ""
        target_id = _uuid(target_raw)
        try:
            page = max(int(page_raw), 0)
        except ValueError:
            page = 0
        if target_id is None or not target_type:
            await callback.answer("Invalid comment target.", show_alert=True)
            return
        async with SessionFactory() as session:
            comments, total = await CommunityService(session, settings).list_comments(
                target_type=target_type,
                target_id=target_id,
                page=page,
            )
        lines = ["💬 <b>COMMENTS</b>", ""]
        if not comments:
            lines.append("No comments have been posted yet.")
        for comment, author in comments:
            lines.extend([f"<b>{escape(author)}</b>", escape(comment.public_body), ""])
        has_next = (page + 1) * 8 < total
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "\n".join(lines).rstrip(),
                reply_markup=comments_keyboard(
                    target_type=target_type,
                    target_id=target_id,
                    page=page,
                    has_next=has_next,
                ),
            )

    @router.callback_query(F.data == "cm:mine")
    async def my_comments(callback: CallbackQuery, db_user: User) -> None:
        async with SessionFactory() as session:
            comments = await CommunityService(session, settings).list_user_comments(
                db_user.id
            )
        lines = ["📝 <b>MY COMMENTS</b>", ""]
        if not comments:
            lines.append("You have not posted any comments yet.")
        for item in comments:
            lines.extend(
                [
                    f"<code>{str(item.id)[:8]}</code> · {item.target_type}",
                    escape(item.public_body[:180]),
                    "",
                ]
            )
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "\n".join(lines).rstrip(),
                reply_markup=my_comments_keyboard([item.id for item in comments]),
            )

    @router.callback_query(F.data.startswith("cm:del:"))
    async def delete_my_comment(callback: CallbackQuery, db_user: User) -> None:
        comment_id = _uuid((callback.data or "").rsplit(":", 1)[-1])
        if comment_id is None:
            await callback.answer("Invalid comment.", show_alert=True)
            return
        async with SessionFactory() as session:
            changed = await CommunityService(session, settings).delete_own_comment(
                comment_id, db_user.id
            )
        await callback.answer(
            "Comment deleted." if changed else "Comment not found.",
            show_alert=True,
        )

    @router.callback_query(F.data.startswith("cm:add:"))
    async def comment_start(callback: CallbackQuery, state: FSMContext) -> None:
        parts = (callback.data or "").split(":")
        if len(parts) != 4:
            await callback.answer("Invalid comment target.", show_alert=True)
            return
        target_short, target_raw = parts[2], parts[3]
        target_type = "title" if target_short == "t" else "release" if target_short == "r" else ""
        target_id = _uuid(target_raw)
        if target_id is None or not target_type:
            await callback.answer("Invalid comment target.", show_alert=True)
            return
        await state.set_state(CommunityStates.comment_body)
        await state.update_data(target_type=target_type, target_id=str(target_id))
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.answer(
                "✍️ <b>WRITE A COMMENT</b>\n\n"
                "Send your comment in one message.\n"
                "Prohibited racial slurs will be replaced with ***.\n\n"
                "Maximum length: 1,000 characters."
            )

    @router.message(CommunityStates.comment_body)
    async def comment_save(message: Message, db_user: User, state: FSMContext) -> None:
        data = await state.get_data()
        target_type = str(data["target_type"])
        target_id = UUID(str(data["target_id"]))
        try:
            async with SessionFactory() as session:
                comment = await CommunityService(session, settings).create_comment(
                    user_id=db_user.id,
                    target_type=target_type,
                    title_id=target_id if target_type == "title" else None,
                    release_id=target_id if target_type == "release" else None,
                    body=message.text or "",
                )
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await state.clear()
        suffix = (
            f"\n\n{comment.replacement_count} prohibited term(s) were replaced with ***."
            if comment.replacement_count
            else ""
        )
        await message.answer(f"✅ <b>COMMENT PUBLISHED</b>{suffix}")

    @router.callback_query(F.data.startswith("community:title_rating:"))
    async def title_rating(callback: CallbackQuery) -> None:
        title_id = _uuid((callback.data or "").rsplit(":", 1)[-1])
        if title_id is None:
            await callback.answer("Invalid title.", show_alert=True)
            return
        async with SessionFactory() as session:
            average, count = await CommunityService(
                session, settings
            ).title_rating_summary(title_id)
        text = (
            f"Overall translation rating: {average:.1f} / 5\nBased on {count} rating(s)."
            if average is not None
            else "This title has not received translation ratings yet."
        )
        await callback.answer(text, show_alert=True)

    @router.callback_query(F.data.startswith("community:rate:"))
    async def rating_start(callback: CallbackQuery) -> None:
        release_id = _uuid((callback.data or "").rsplit(":", 1)[-1])
        if release_id is None:
            await callback.answer("Invalid release.", show_alert=True)
            return
        async with SessionFactory() as session:
            average, count = await CommunityService(session, settings).rating_summary(
                release_id
            )
        summary = (
            f"Current rating: <b>{average:.1f} / 5</b> based on {count} rating(s).\n\n"
            if average is not None
            else "No ratings have been submitted yet.\n\n"
        )
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "⭐ <b>RATE THIS TRANSLATION</b>\n\n"
                + summary
                + "How would you rate the translation quality?",
                reply_markup=rating_stars_keyboard(release_id),
            )

    @router.callback_query(F.data.startswith("cm:rs:"))
    async def rating_score(callback: CallbackQuery, state: FSMContext) -> None:
        parts = (callback.data or "").split(":")
        release_id = _uuid(parts[2]) if len(parts) == 4 else None
        try:
            score = int(parts[3]) if len(parts) == 4 else 0
        except ValueError:
            score = 0
        if release_id is None or score not in range(1, 6):
            await callback.answer("Invalid rating.", show_alert=True)
            return
        await state.update_data(
            rating_release_id=str(release_id),
            rating_score=score,
            rating_categories=[],
        )
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "🧩 <b>WHAT NEEDS IMPROVEMENT?</b>\n\n"
                "Select at least one category.",
                reply_markup=rating_categories_keyboard(release_id, set(), score),
            )

    @router.callback_query(F.data.startswith("cm:rc:"))
    async def rating_category(callback: CallbackQuery, state: FSMContext) -> None:
        parts = (callback.data or "").split(":")
        if len(parts) != 4:
            await callback.answer("Invalid category.", show_alert=True)
            return
        release_id = _uuid(parts[2])
        code = parts[3]
        if release_id is None or code not in RATING_CATEGORY_LABELS:
            await callback.answer("Invalid category.", show_alert=True)
            return
        data = await state.get_data()
        score = int(data.get("rating_score", 0))
        selected = set(data.get("rating_categories", []))
        if code in selected:
            selected.remove(code)
        elif code == "no_issues":
            selected = {"no_issues"}
        else:
            selected.discard("no_issues")
            selected.add(code)
        await state.update_data(rating_categories=sorted(selected))
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(
                reply_markup=rating_categories_keyboard(release_id, selected, score)
            )

    @router.callback_query(F.data.startswith("cm:rd:"))
    async def rating_categories_done(
        callback: CallbackQuery, state: FSMContext
    ) -> None:
        release_id = _uuid((callback.data or "").rsplit(":", 1)[-1])
        data = await state.get_data()
        selected = list(data.get("rating_categories", []))
        if release_id is None or not selected:
            await callback.answer("Select at least one category.", show_alert=True)
            return
        await state.set_state(CommunityStates.rating_feedback)
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "📝 <b>DESCRIBE THE TRANSLATION</b>\n\n"
                "Explain what felt wrong or what was done well.\n"
                "Mention a chapter, scene or phrase when possible.\n\n"
                "Minimum: 20 characters\nMaximum: 2,000 characters."
            )

    @router.message(CommunityStates.rating_feedback)
    async def rating_feedback(
        message: Message, db_user: User, state: FSMContext
    ) -> None:
        data = await state.get_data()
        try:
            async with SessionFactory() as session:
                rating = await CommunityService(session, settings).save_rating(
                    user_id=db_user.id,
                    release_id=UUID(str(data["rating_release_id"])),
                    score=int(data["rating_score"]),
                    category_codes=list(data["rating_categories"]),
                    feedback=message.text or "",
                )
        except (KeyError, ValueError) as exc:
            await message.answer(str(exc))
            return
        await state.clear()
        await message.answer(
            "✅ <b>RATING SUBMITTED</b>\n\n"
            f"Your rating: <b>{rating.score} of 5</b>\n"
            "Your feedback has been sent to the translation team."
        )

    @router.callback_query(F.data.startswith("community:report:"))
    async def report_start(callback: CallbackQuery) -> None:
        parts = (callback.data or "").split(":")
        if len(parts) != 4:
            await callback.answer("Invalid report target.", show_alert=True)
            return
        target_type, target_raw = parts[2], parts[3]
        target_id = _uuid(target_raw)
        if target_id is None or target_type not in {"title", "release"}:
            await callback.answer("Invalid report target.", show_alert=True)
            return
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "⚠️ <b>REPORT A PROBLEM</b>\n\nWhat is the problem?",
                reply_markup=report_categories_keyboard(target_type, target_id),
            )

    @router.callback_query(F.data.startswith("cm:pc:"))
    async def report_category(callback: CallbackQuery, state: FSMContext) -> None:
        parts = (callback.data or "").split(":")
        if len(parts) != 5:
            await callback.answer("Invalid report category.", show_alert=True)
            return
        target_short, target_raw, category = parts[2], parts[3], parts[4]
        target_type = "title" if target_short == "t" else "release" if target_short == "r" else ""
        target_id = _uuid(target_raw)
        if target_id is None or not target_type:
            await callback.answer("Invalid report target.", show_alert=True)
            return
        await state.set_state(CommunityStates.report_body)
        await state.update_data(
            report_target_type=target_type,
            report_target_id=str(target_id),
            report_category=category,
        )
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "📝 <b>DESCRIBE THE PROBLEM</b>\n\n"
                "Send a text description. You may attach one document or photo up to 20 MB.\n\n"
                "Refunds are not provided."
            )

    @router.message(CommunityStates.report_body)
    async def report_save(
        message: Message, db_user: User, state: FSMContext, bot: Bot
    ) -> None:
        data = await state.get_data()
        attachment: dict[str, object] | None = None
        description = message.text or message.caption or ""
        if message.document is not None:
            attachment = {
                "telegram_file_id": message.document.file_id,
                "telegram_file_unique_id": message.document.file_unique_id,
                "filename": message.document.file_name,
                "content_type": message.document.mime_type,
                "size_bytes": message.document.file_size or 0,
            }
        elif message.photo:
            photo = message.photo[-1]
            attachment = {
                "telegram_file_id": photo.file_id,
                "telegram_file_unique_id": photo.file_unique_id,
                "filename": "report-photo.jpg",
                "content_type": "image/jpeg",
                "size_bytes": photo.file_size or 0,
            }
        try:
            async with SessionFactory() as session:
                report = await CommunityService(session, settings).create_report(
                    user_id=db_user.id,
                    target_type=str(data["report_target_type"]),
                    title_id=(
                        UUID(str(data["report_target_id"]))
                        if data["report_target_type"] == "title"
                        else None
                    ),
                    release_id=(
                        UUID(str(data["report_target_id"]))
                        if data["report_target_type"] == "release"
                        else None
                    ),
                    category=str(data["report_category"]),
                    description=description,
                    attachment=attachment,
                )
        except (KeyError, ValueError) as exc:
            await message.answer(str(exc))
            return
        await state.clear()
        await message.answer(
            "✅ <b>REPORT SUBMITTED</b>\n\n"
            f"Report ID: <code>{report.id}</code>\n"
            "Status: Open\n\nReports are reviewed individually. The bot does not issue refunds."
        )
        await bot.send_message(
            settings.admin_telegram_id,
            "⚠️ <b>NEW REPORT</b>\n\n"
            f"ID: <code>{report.id}</code>\n"
            f"Category: {escape(report.category)}\n"
            f"User: {db_user.telegram_id}",
        )

    return router
