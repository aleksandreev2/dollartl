from __future__ import annotations

from html import escape
from uuid import UUID

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from dollartl.bot.suggestion_keyboards import (
    publication_status_keyboard,
    review_keyboard,
    rules_keyboard,
    skip_file_keyboard,
    start_keyboard,
    suggestion_view_keyboard,
    suggestions_list_keyboard,
)
from dollartl.bot.suggestion_upload import upload_suggestion_file
from dollartl.config import Settings
from dollartl.db.models import User
from dollartl.db.session import SessionFactory
from dollartl.services.suggestion_helpers import parse_source_lines
from dollartl.services.suggestions import PUBLIC_STATUS, SuggestionService


class SuggestionStates(StatesGroup):
    title = State()
    sources = State()
    chapter_count = State()
    publication_status = State()
    raw_file = State()
    cover = State()
    review = State()


def _uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except (TypeError, ValueError):
        return None


async def _answer_or_edit(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=reply_markup)


def _rules_text(settings: Settings) -> str:
    return (
        "⚠️ <b>TITLE SUGGESTION RULES</b>\n\n"
        "Do not suggest novels containing:\n\n"
        "• guro or extreme sexualized gore;\n"
        "• scat or feces-related sexual content;\n"
        "• sexual content involving minors.\n\n"
        "Repeated violations may result in your entire account being temporarily or permanently blocked.\n\n"
        f"Rules version: {settings.suggestion_rules_version}"
    )


async def _start_wizard(
    callback: CallbackQuery,
    state: FSMContext,
    db_user: User,
    settings: Settings,
) -> None:
    async with SessionFactory() as session:
        service = SuggestionService(session, settings)
        quota = await service.quota_snapshot(db_user)
        if quota.remaining < 1:
            await _answer_or_edit(
                callback,
                "⛔ <b>MONTHLY LIMIT REACHED</b>\n\n"
                f"Suggestions used: {quota.used} of {quota.limit}\n\n"
                "Your quota resets on the first day of the next calendar month.",
                start_keyboard(),
            )
            return
        draft = await service.get_or_create_draft(db_user)
    await state.set_state(SuggestionStates.title)
    await state.update_data(suggestion_id=str(draft.id))
    await _answer_or_edit(
        callback,
        "<b>STEP 1 OF 6 — ORIGINAL TITLE</b>\n\n"
        "Send the title exactly as it appears in the original language.",
    )


async def _show_review(
    message_or_callback: Message | CallbackQuery,
    state: FSMContext,
    settings: Settings,
) -> None:
    data = await state.get_data()
    suggestion_id = _uuid(str(data.get("suggestion_id", "")))
    if suggestion_id is None:
        text = "Suggestion draft could not be found."
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.answer(text, show_alert=True)
        else:
            await message_or_callback.answer(text)
        return
    async with SessionFactory() as session:
        payload = await SuggestionService(session, settings).review(suggestion_id)
    suggestion = payload.suggestion
    files_by_kind = {item.file_kind: item for item in payload.files}
    scope_end = suggestion.chapter_count
    if not suggestion.vip_snapshot and suggestion.chapter_count:
        scope_end = min(
            suggestion.chapter_count,
            settings.suggestion_standard_chapter_limit,
        )
    raw_name = (
        escape(files_by_kind["raw"].original_filename)
        if "raw" in files_by_kind
        else "Not attached"
    )
    cover_name = (
        escape(files_by_kind["cover"].original_filename)
        if "cover" in files_by_kind
        else "Not attached"
    )
    text = (
        "<b>STEP 6 OF 6 — REVIEW</b>\n\n"
        f"<b>Original title:</b>\n{escape(suggestion.original_title or 'Missing')}\n\n"
        f"<b>Detected language:</b> {escape(suggestion.detected_language or 'Unknown')}\n"
        f"<b>Source links:</b> {len(payload.sources)}\n"
        f"<b>Current chapters:</b> {suggestion.chapter_count or 'Missing'}\n"
        f"<b>Publication status:</b> {escape(suggestion.publication_status or 'Missing')}\n"
        f"<b>Requested translation scope:</b> 1–{scope_end or '?'}\n"
        f"<b>Raw file:</b> {raw_name}\n"
        f"<b>Cover:</b> {cover_name}\n\n"
        "Review the details before submitting. A submitted suggestion uses one monthly slot."
    )
    await state.set_state(SuggestionStates.review)
    if isinstance(message_or_callback, CallbackQuery):
        await _answer_or_edit(message_or_callback, text, review_keyboard(suggestion_id))
    else:
        await message_or_callback.answer(text, reply_markup=review_keyboard(suggestion_id))


def create_suggestion_router(settings: Settings) -> Router:
    router = Router(name="suggestions")

    @router.callback_query(F.data == "menu:suggest")
    async def suggestion_menu(callback: CallbackQuery, db_user: User) -> None:
        async with SessionFactory() as session:
            service = SuggestionService(session, settings)
            consent = await service.has_rules_consent(db_user.id)
            quota = await service.quota_snapshot(db_user)
        if not consent:
            await _answer_or_edit(callback, _rules_text(settings), rules_keyboard())
            return
        level = "[VIP]" if quota.vip else "Standard"
        await _answer_or_edit(
            callback,
            "💡 <b>SUGGEST A TITLE</b>\n\n"
            f"Account level: <b>{level}</b>\n"
            f"Suggestions used: <b>{quota.used} of {quota.limit}</b>\n\n"
            "Drafts do not use quota. A slot is used only after submission.",
            start_keyboard(),
        )

    @router.callback_query(F.data == "sug:rules:accept")
    async def accept_rules_start(
        callback: CallbackQuery,
        db_user: User,
        state: FSMContext,
    ) -> None:
        async with SessionFactory() as session:
            await SuggestionService(session, settings).accept_rules(db_user.id)
        await _start_wizard(callback, state, db_user, settings)

    @router.callback_query(F.data == "sug:start")
    async def start(
        callback: CallbackQuery,
        db_user: User,
        state: FSMContext,
    ) -> None:
        await _start_wizard(callback, state, db_user, settings)

    @router.message(SuggestionStates.title)
    async def title_step(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        suggestion_id = _uuid(str(data.get("suggestion_id", "")))
        if suggestion_id is None:
            await message.answer("Suggestion draft could not be found.")
            return
        try:
            async with SessionFactory() as session:
                await SuggestionService(session, settings).set_title(
                    suggestion_id,
                    message.text or "",
                )
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await state.set_state(SuggestionStates.sources)
        await message.answer(
            "<b>STEP 2 OF 6 — SOURCE LINKS</b>\n\n"
            "Send at least one link to the original novel. Put each URL on a separate line."
        )

    @router.message(SuggestionStates.sources)
    async def sources_step(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        suggestion_id = _uuid(str(data.get("suggestion_id", "")))
        try:
            sources = parse_source_lines(
                message.text or "",
                settings.suggestion_source_max,
            )
            if suggestion_id is None:
                raise ValueError("Suggestion draft could not be found.")
            async with SessionFactory() as session:
                await SuggestionService(session, settings).set_sources(
                    suggestion_id,
                    sources,
                )
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await state.set_state(SuggestionStates.chapter_count)
        await message.answer(
            "<b>STEP 3 OF 6 — CHAPTER COUNT</b>\n\n"
            "How many chapters does the novel currently have? Send one whole number."
        )

    @router.message(SuggestionStates.chapter_count)
    async def chapter_step(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        suggestion_id = _uuid(str(data.get("suggestion_id", "")))
        try:
            count = int((message.text or "").strip())
            if suggestion_id is None:
                raise ValueError("Suggestion draft could not be found.")
            async with SessionFactory() as session:
                await SuggestionService(session, settings).set_chapter_count(
                    suggestion_id,
                    count,
                )
        except (ValueError, TypeError) as exc:
            await message.answer(str(exc) if str(exc) else "Send a valid whole number.")
            return
        await state.set_state(SuggestionStates.publication_status)
        await message.answer(
            "<b>STEP 3 OF 6 — PUBLICATION STATUS</b>\n\n"
            "Choose the current publication status.",
            reply_markup=publication_status_keyboard(),
        )

    @router.callback_query(F.data.startswith("sug:pub:"))
    async def publication_step(callback: CallbackQuery, state: FSMContext) -> None:
        status = (callback.data or "").rsplit(":", 1)[-1]
        data = await state.get_data()
        suggestion_id = _uuid(str(data.get("suggestion_id", "")))
        try:
            if suggestion_id is None:
                raise ValueError("Suggestion draft could not be found.")
            async with SessionFactory() as session:
                await SuggestionService(session, settings).set_publication_status(
                    suggestion_id,
                    status,
                )
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        await state.set_state(SuggestionStates.raw_file)
        await _answer_or_edit(
            callback,
            "<b>STEP 4 OF 6 — RAW FILE</b>\n\n"
            "Upload an EPUB, TXT, ZIP, DOCX or PDF raw file if available.\n"
            "Maximum: 20 MB.",
            skip_file_keyboard("raw"),
        )

    @router.message(SuggestionStates.raw_file)
    async def raw_step(message: Message, state: FSMContext, bot: Bot) -> None:
        try:
            await upload_suggestion_file(
                message=message,
                bot=bot,
                state=state,
                settings=settings,
                file_kind="raw",
            )
        except ValueError as exc:
            await message.answer(str(exc), reply_markup=skip_file_keyboard("raw"))
            return
        await state.set_state(SuggestionStates.cover)
        await message.answer(
            "<b>STEP 5 OF 6 — OFFICIAL COVER</b>\n\n"
            "Upload a JPG, PNG or WebP cover if available.",
            reply_markup=skip_file_keyboard("cover"),
        )

    @router.callback_query(F.data == "sug:skip:raw")
    async def skip_raw(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(SuggestionStates.cover)
        await _answer_or_edit(
            callback,
            "<b>STEP 5 OF 6 — OFFICIAL COVER</b>\n\n"
            "Upload a JPG, PNG or WebP cover if available.",
            skip_file_keyboard("cover"),
        )

    @router.message(SuggestionStates.cover)
    async def cover_step(message: Message, state: FSMContext, bot: Bot) -> None:
        try:
            await upload_suggestion_file(
                message=message,
                bot=bot,
                state=state,
                settings=settings,
                file_kind="cover",
            )
        except ValueError as exc:
            await message.answer(str(exc), reply_markup=skip_file_keyboard("cover"))
            return
        await _show_review(message, state, settings)

    @router.callback_query(F.data == "sug:skip:cover")
    async def skip_cover(callback: CallbackQuery, state: FSMContext) -> None:
        await _show_review(callback, state, settings)

    @router.callback_query(F.data.startswith("sug:submit:"))
    async def submit(
        callback: CallbackQuery,
        db_user: User,
        state: FSMContext,
        bot: Bot,
    ) -> None:
        suggestion_id = _uuid((callback.data or "").rsplit(":", 1)[-1])
        if suggestion_id is None:
            await callback.answer("Invalid suggestion.", show_alert=True)
            return
        try:
            async with SessionFactory() as session:
                suggestion = await SuggestionService(session, settings).submit(
                    suggestion_id,
                    db_user,
                )
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        await state.clear()
        scope_note = ""
        if (
            suggestion.chapter_count
            and suggestion.requested_chapter_end != suggestion.chapter_count
        ):
            scope_note = (
                f"\nRequested translation scope: chapters 1–"
                f"{suggestion.requested_chapter_end}."
            )
        await _answer_or_edit(
            callback,
            "✅ <b>SUGGESTION SUBMITTED</b>\n\n"
            f"Suggestion ID: <code>{suggestion.id}</code>\n"
            "Status: <b>Under Review</b>"
            f"{scope_note}",
            start_keyboard(),
        )
        duplicate = (
            "required" if suggestion.duplicate_review_required else "not detected"
        )
        await bot.send_message(
            settings.admin_telegram_id,
            "💡 <b>NEW TITLE SUGGESTION</b>\n\n"
            f"ID: <code>{suggestion.id}</code>\n"
            f"Title: {escape(suggestion.original_title or '')}\n"
            f"User: {db_user.telegram_id}\n"
            f"VIP snapshot: {'yes' if suggestion.vip_snapshot else 'no'}\n"
            f"Duplicate review: {duplicate}",
        )

    @router.callback_query(F.data == "sug:mine")
    async def mine(callback: CallbackQuery, db_user: User) -> None:
        async with SessionFactory() as session:
            items = await SuggestionService(session, settings).list_user(db_user.id)
        text = "📋 <b>MY SUGGESTIONS</b>\n\nChoose a suggestion to view its status."
        if not items:
            text += "\n\nYou have not submitted any suggestions yet."
        await _answer_or_edit(callback, text, suggestions_list_keyboard(items))

    @router.callback_query(F.data.startswith("sug:view:"))
    async def view(callback: CallbackQuery, db_user: User) -> None:
        suggestion_id = _uuid((callback.data or "").rsplit(":", 1)[-1])
        async with SessionFactory() as session:
            suggestion = (
                await SuggestionService(session, settings).get(suggestion_id)
                if suggestion_id
                else None
            )
        if (
            suggestion is None
            or suggestion.user_id != db_user.id
            or suggestion.status == "draft"
        ):
            await callback.answer("Suggestion not found.", show_alert=True)
            return
        reason = (
            f"\n\n<b>Reason:</b>\n{escape(suggestion.public_reason)}"
            if suggestion.public_reason
            else ""
        )
        await _answer_or_edit(
            callback,
            "💡 <b>TITLE SUGGESTION</b>\n\n"
            f"<b>{escape(suggestion.original_title or 'Untitled')}</b>\n"
            f"Status: <b>{PUBLIC_STATUS.get(suggestion.status, suggestion.status)}</b>\n"
            f"Chapters: {suggestion.chapter_count or '?'}\n"
            f"Requested scope: {suggestion.requested_chapter_start}–"
            f"{suggestion.requested_chapter_end or '?'}"
            f"{reason}",
            suggestion_view_keyboard(suggestion.linked_title_id),
        )

    @router.callback_query(F.data == "sug:cancel")
    async def cancel(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await _answer_or_edit(
            callback,
            "Draft paused. It did not use a monthly suggestion slot.",
            start_keyboard(),
        )

    return router
