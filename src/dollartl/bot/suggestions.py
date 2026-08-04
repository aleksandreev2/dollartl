from __future__ import annotations

from html import escape
from uuid import UUID

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from dollartl.bot.suggestion_keyboards import publication_status_keyboard, review_keyboard, rules_keyboard, skip_file_keyboard, start_keyboard, suggestion_view_keyboard, suggestions_list_keyboard
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


async def _edit(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=reply_markup)


def _rules(settings: Settings) -> str:
    return (
        "⚠️ <b>TITLE SUGGESTION RULES</b>\n\n"
        "Do not suggest novels containing:\n\n"
        "• guro or extreme sexualized gore;\n"
        "• scat or feces-related sexual content;\n"
        "• sexual content involving minors.\n\n"
        "A valid raw source file is required for every suggestion.\n"
        "Repeated violations may result in a temporary or permanent account block.\n\n"
        f"Rules version: {settings.suggestion_rules_version}"
    )


async def _begin(callback: CallbackQuery, state: FSMContext, user: User, settings: Settings) -> None:
    async with SessionFactory() as session:
        service = SuggestionService(session, settings)
        quota = await service.quota_snapshot(user)
        if quota.remaining < 1:
            await _edit(callback, "⛔ <b>MONTHLY LIMIT REACHED</b>\n\n" f"Suggestions used: {quota.used} of {quota.limit}\n\nYour quota resets on the first day of the next calendar month.", start_keyboard())
            return
        draft = await service.get_or_create_draft(user)
    await state.set_state(SuggestionStates.title)
    await state.update_data(suggestion_id=str(draft.id))
    await _edit(callback, "<b>STEP 1 OF 6 — ORIGINAL TITLE</b>\n\nSend the title exactly as it appears in the original language.")


async def _review(target: Message | CallbackQuery, state: FSMContext, settings: Settings) -> None:
    data = await state.get_data()
    suggestion_id = _uuid(str(data.get("suggestion_id", "")))
    if suggestion_id is None:
        text = "Suggestion draft could not be found."
        if isinstance(target, CallbackQuery):
            await target.answer(text, show_alert=True)
        else:
            await target.answer(text)
        return
    async with SessionFactory() as session:
        details = await SuggestionService(session, settings).review(suggestion_id)
    suggestion = details.suggestion
    files = {item.file_kind: item for item in details.files}
    raw = files.get("raw")
    if raw is None or raw.validation_status != "valid":
        await state.set_state(SuggestionStates.raw_file)
        text = "A validated raw file is required before review and submission."
        if isinstance(target, CallbackQuery):
            await _edit(target, text, skip_file_keyboard("raw"))
        else:
            await target.answer(text, reply_markup=skip_file_keyboard("raw"))
        return
    scope_end = suggestion.chapter_count
    if not suggestion.vip_snapshot and suggestion.chapter_count:
        scope_end = min(suggestion.chapter_count, settings.suggestion_standard_chapter_limit)
    cover = files.get("cover")
    text = (
        "<b>STEP 6 OF 6 — REVIEW</b>\n\n"
        f"<b>Original title:</b>\n{escape(suggestion.original_title or 'Missing')}\n\n"
        f"<b>Detected language:</b> {escape(suggestion.detected_language or 'Unknown')}\n"
        f"<b>Source links:</b> {len(details.sources)}\n"
        f"<b>Current chapters:</b> {suggestion.chapter_count or 'Missing'}\n"
        f"<b>Publication status:</b> {escape(suggestion.publication_status or 'Missing')}\n"
        f"<b>Requested translation scope:</b> 1–{scope_end or '?'}\n"
        f"<b>Raw file:</b> {escape(raw.original_filename)} — validated\n"
        f"<b>Cover:</b> {escape(cover.original_filename) if cover else 'Not attached'}\n\n"
        "Submitting uses one monthly slot."
    )
    await state.set_state(SuggestionStates.review)
    if isinstance(target, CallbackQuery):
        await _edit(target, text, review_keyboard(suggestion_id))
    else:
        await target.answer(text, reply_markup=review_keyboard(suggestion_id))


def create_suggestion_router(settings: Settings) -> Router:
    router = Router(name="suggestions")

    @router.callback_query(F.data == "menu:suggest")
    async def menu(callback: CallbackQuery, db_user: User) -> None:
        async with SessionFactory() as session:
            service = SuggestionService(session, settings)
            consent = await service.has_rules_consent(db_user.id)
            quota = await service.quota_snapshot(db_user)
        if not consent:
            await _edit(callback, _rules(settings), rules_keyboard())
            return
        level = "[VIP]" if quota.vip else "Standard"
        await _edit(callback, "💡 <b>SUGGEST A TITLE</b>\n\n" f"Account level: <b>{level}</b>\nSuggestions used: <b>{quota.used} of {quota.limit}</b>\n\nA validated raw file is mandatory. Drafts do not use quota.", start_keyboard())

    @router.callback_query(F.data == "sug:rules:accept")
    async def accept(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
        async with SessionFactory() as session:
            await SuggestionService(session, settings).accept_rules(db_user.id)
        await _begin(callback, state, db_user, settings)

    @router.callback_query(F.data == "sug:start")
    async def start(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
        await _begin(callback, state, db_user, settings)

    @router.message(SuggestionStates.title)
    async def title(message: Message, state: FSMContext) -> None:
        suggestion_id = _uuid(str((await state.get_data()).get("suggestion_id", "")))
        try:
            if suggestion_id is None:
                raise ValueError("Suggestion draft could not be found.")
            async with SessionFactory() as session:
                await SuggestionService(session, settings).set_title(suggestion_id, message.text or "")
        except ValueError as exc:
            await message.answer(str(exc)); return
        await state.set_state(SuggestionStates.sources)
        await message.answer("<b>STEP 2 OF 6 — SOURCE LINKS</b>\n\nSend at least one original-novel URL, one per line.")

    @router.message(SuggestionStates.sources)
    async def sources(message: Message, state: FSMContext) -> None:
        suggestion_id = _uuid(str((await state.get_data()).get("suggestion_id", "")))
        try:
            values = parse_source_lines(message.text or "", settings.suggestion_source_max)
            if suggestion_id is None:
                raise ValueError("Suggestion draft could not be found.")
            async with SessionFactory() as session:
                await SuggestionService(session, settings).set_sources(suggestion_id, values)
        except ValueError as exc:
            await message.answer(str(exc)); return
        await state.set_state(SuggestionStates.chapter_count)
        await message.answer("<b>STEP 3 OF 6 — CHAPTER COUNT</b>\n\nSend the current chapter count as a whole number.")

    @router.message(SuggestionStates.chapter_count)
    async def chapter_count(message: Message, state: FSMContext) -> None:
        suggestion_id = _uuid(str((await state.get_data()).get("suggestion_id", "")))
        try:
            if suggestion_id is None:
                raise ValueError("Suggestion draft could not be found.")
            async with SessionFactory() as session:
                await SuggestionService(session, settings).set_chapter_count(suggestion_id, int((message.text or "").strip()))
        except (ValueError, TypeError) as exc:
            await message.answer(str(exc) or "Send a valid number."); return
        await state.set_state(SuggestionStates.publication_status)
        await message.answer("<b>STEP 3 OF 6 — PUBLICATION STATUS</b>\n\nChoose the current status.", reply_markup=publication_status_keyboard())

    @router.callback_query(F.data.startswith("sug:pub:"))
    async def publication(callback: CallbackQuery, state: FSMContext) -> None:
        suggestion_id = _uuid(str((await state.get_data()).get("suggestion_id", "")))
        try:
            if suggestion_id is None:
                raise ValueError("Suggestion draft could not be found.")
            async with SessionFactory() as session:
                await SuggestionService(session, settings).set_publication_status(suggestion_id, (callback.data or "").rsplit(":", 1)[-1])
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True); return
        await state.set_state(SuggestionStates.raw_file)
        await _edit(callback, "<b>STEP 4 OF 6 — RAW FILE</b>\n\nUpload EPUB, TXT, ZIP, DOCX or PDF. This step is required. Maximum: 20 MB.", skip_file_keyboard("raw"))

    @router.message(SuggestionStates.raw_file)
    async def raw_file(message: Message, state: FSMContext, bot: Bot) -> None:
        try:
            await upload_suggestion_file(message=message, bot=bot, state=state, settings=settings, file_kind="raw")
        except ValueError as exc:
            await message.answer(str(exc), reply_markup=skip_file_keyboard("raw")); return
        await state.set_state(SuggestionStates.cover)
        await message.answer("<b>STEP 5 OF 6 — OFFICIAL COVER</b>\n\nUpload JPG, PNG or WebP, or skip this optional step.", reply_markup=skip_file_keyboard("cover"))

    @router.callback_query(F.data == "sug:skip:raw")
    async def cannot_skip_raw(callback: CallbackQuery) -> None:
        await callback.answer("A raw file is required and cannot be skipped.", show_alert=True)

    @router.message(SuggestionStates.cover)
    async def cover(message: Message, state: FSMContext, bot: Bot) -> None:
        try:
            await upload_suggestion_file(message=message, bot=bot, state=state, settings=settings, file_kind="cover")
        except ValueError as exc:
            await message.answer(str(exc), reply_markup=skip_file_keyboard("cover")); return
        await _review(message, state, settings)

    @router.callback_query(F.data == "sug:skip:cover")
    async def skip_cover(callback: CallbackQuery, state: FSMContext) -> None:
        await _review(callback, state, settings)

    @router.callback_query(F.data.startswith("sug:submit:"))
    async def submit(callback: CallbackQuery, db_user: User, state: FSMContext, bot: Bot) -> None:
        suggestion_id = _uuid((callback.data or "").rsplit(":", 1)[-1])
        try:
            if suggestion_id is None:
                raise ValueError("Invalid suggestion.")
            async with SessionFactory() as session:
                service = SuggestionService(session, settings)
                details = await service.review(suggestion_id)
                raw = next((item for item in details.files if item.file_kind == "raw"), None)
                if raw is None or raw.validation_status != "valid":
                    raise ValueError("A validated raw file is required before submission.")
                suggestion = await service.submit(suggestion_id, db_user)
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True); return
        await state.clear()
        await _edit(callback, "✅ <b>SUGGESTION SUBMITTED</b>\n\n" f"Suggestion ID: <code>{suggestion.id}</code>\nStatus: <b>Under Review</b>", start_keyboard())
        await bot.send_message(settings.admin_telegram_id, "💡 <b>NEW TITLE SUGGESTION</b>\n\n" f"ID: <code>{suggestion.id}</code>\nTitle: {escape(suggestion.original_title or '')}\nUser: {db_user.telegram_id}\nRaw file: validated")

    @router.callback_query(F.data == "sug:mine")
    async def mine(callback: CallbackQuery, db_user: User) -> None:
        async with SessionFactory() as session:
            items = await SuggestionService(session, settings).list_user(db_user.id)
        text = "📋 <b>MY SUGGESTIONS</b>\n\nChoose a suggestion to view its status."
        if not items:
            text += "\n\nYou have not submitted any suggestions yet."
        await _edit(callback, text, suggestions_list_keyboard(items))

    @router.callback_query(F.data.startswith("sug:view:"))
    async def view(callback: CallbackQuery, db_user: User) -> None:
        suggestion_id = _uuid((callback.data or "").rsplit(":", 1)[-1])
        async with SessionFactory() as session:
            item = await SuggestionService(session, settings).get(suggestion_id) if suggestion_id else None
        if item is None or item.user_id != db_user.id or item.status == "draft":
            await callback.answer("Suggestion not found.", show_alert=True); return
        reason = f"\n\n<b>Reason:</b>\n{escape(item.public_reason)}" if item.public_reason else ""
        await _edit(callback, "💡 <b>TITLE SUGGESTION</b>\n\n" f"<b>{escape(item.original_title or 'Untitled')}</b>\nStatus: <b>{PUBLIC_STATUS.get(item.status, item.status)}</b>\nChapters: {item.chapter_count or '?'}\nRequested scope: {item.requested_chapter_start}–{item.requested_chapter_end or '?'}{reason}", suggestion_view_keyboard(item.linked_title_id))

    @router.callback_query(F.data == "sug:cancel")
    async def cancel(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await _edit(callback, "Draft paused. It did not use a monthly suggestion slot.", start_keyboard())

    return router
