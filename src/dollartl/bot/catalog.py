from __future__ import annotations

import asyncio
import tempfile
from html import escape
from pathlib import Path
from uuid import UUID

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, Message

from dollartl.bot.keyboards import (
    NAV_SEARCH,
    catalogue_keyboard,
    home_keyboard,
    latest_keyboard,
    library_keyboard,
    release_keyboard,
    search_prompt_keyboard,
    search_results_keyboard,
    title_keyboard,
)
from dollartl.bot.texts import (
    NO_RELEASES,
    NO_SEARCH_RESULTS,
    NO_TITLES,
    render_release,
    render_title,
)
from dollartl.config import Settings
from dollartl.db.models import Release, Title, User
from dollartl.db.session import SessionFactory
from dollartl.services.catalog import CatalogService, ReleaseFileBundle
from dollartl.storage import S3Storage


class SearchTitleState(StatesGroup):
    query = State()


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


async def _edit_or_answer(
    callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup
) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(text, reply_markup=reply_markup)
        except TelegramBadRequest:
            await callback.message.answer(text, reply_markup=reply_markup)


async def _show_catalogue(callback: CallbackQuery, settings: Settings, page: int) -> None:
    async with SessionFactory() as session:
        service = CatalogService(session)
        titles = await service.list_titles(page=page, page_size=settings.catalogue_page_size)
        count = await service.count_titles()
    has_next = (page + 1) * settings.catalogue_page_size < count
    text = "📚 <b>BROWSE TITLES</b>\n\nChoose a title or search by name."
    if not titles:
        text = f"📚 <b>BROWSE TITLES</b>\n\n{NO_TITLES}"
    await _edit_or_answer(
        callback,
        text,
        catalogue_keyboard(titles, page=page, has_next=has_next),
    )


async def _show_latest(callback: CallbackQuery, settings: Settings, page: int) -> None:
    async with SessionFactory() as session:
        service = CatalogService(session)
        releases = await service.latest_releases(
            page=page, page_size=settings.catalogue_page_size + 1
        )
        has_next = len(releases) > settings.catalogue_page_size
        releases = releases[: settings.catalogue_page_size]
        titles: dict[UUID, Title] = {}
        for release in releases:
            titles[release.title_id] = await service.title_for_release(release)
    text = "🆕 <b>LATEST RELEASES</b>\n\nChoose a chapter package."
    if not releases:
        text = "🆕 <b>LATEST RELEASES</b>\n\nNo releases have been published yet."
    await _edit_or_answer(
        callback,
        text,
        latest_keyboard(releases, titles, page=page, has_next=has_next),
    )


async def _show_title_by_id(
    callback: CallbackQuery, title_id: UUID, db_user: User, *, answer_callback: bool = True
) -> None:
    async with SessionFactory() as session:
        service = CatalogService(session)
        title = await service.get_title(title_id, published_only=True)
        if title is None:
            await callback.answer("Title not found.", show_alert=True)
            return
        releases = await service.list_releases(title.id)
        followed = await service.is_following(db_user.id, title.id)
    text = render_title(title)
    if not releases:
        text += f"\n\n{NO_RELEASES}"
    if answer_callback:
        await _edit_or_answer(
            callback,
            text,
            title_keyboard(title, releases, followed=followed),
        )
    elif isinstance(callback.message, Message):
        await callback.message.edit_text(
            text, reply_markup=title_keyboard(title, releases, followed=followed)
        )


async def _show_release_by_id(
    callback: CallbackQuery, release_id: UUID, db_user: User, settings: Settings
) -> None:
    async with SessionFactory() as session:
        service = CatalogService(session)
        release = await service.get_release(release_id, published_only=True)
        if release is None:
            await callback.answer("Release not found.", show_alert=True)
            return
        title = await service.title_for_release(release)
        direct = await service.can_download_directly(db_user, settings.admin_telegram_id)
    await _edit_or_answer(
        callback,
        render_release(title, release),
        release_keyboard(
            release,
            direct_download=direct,
            boosty_url=release.boosty_url or title.boosty_url,
        ),
    )


async def send_deep_link_target(
    *, bot: Bot, chat_id: int, token: str, db_user: User, settings: Settings
) -> bool:
    async with SessionFactory() as session:
        service = CatalogService(session)
        target = await service.resolve_deep_link(token)
        if target is None:
            return False
        if target.target_type == "title" and target.title_id is not None:
            title = await service.get_title(target.title_id, published_only=True)
            if title is None:
                return False
            releases = await service.list_releases(title.id)
            followed = await service.is_following(db_user.id, title.id)
            await bot.send_message(
                chat_id,
                render_title(title),
                reply_markup=title_keyboard(title, releases, followed=followed),
            )
            return True
        if target.target_type == "release" and target.release_id is not None:
            release = await service.get_release(target.release_id, published_only=True)
            if release is None:
                return False
            title = await service.title_for_release(release)
            direct = await service.can_download_directly(db_user, settings.admin_telegram_id)
            await bot.send_message(
                chat_id,
                render_release(title, release),
                reply_markup=release_keyboard(
                    release,
                    direct_download=direct,
                    boosty_url=release.boosty_url or title.boosty_url,
                ),
            )
            return True
    return False


async def _send_file_bundle(
    *,
    bot: Bot,
    chat_id: int,
    user_id: UUID,
    bundle: ReleaseFileBundle,
    release: Release,
    title: Title,
    settings: Settings,
) -> None:
    version = bundle.version
    caption = (
        f"<b>{title.english_title}</b> — {release.chapter_label}\n"
        f"Format: {bundle.release_file.file_kind.upper()}\n"
        "Protected subscriber copy"
    )
    document: str | FSInputFile
    temp_path: Path | None = None
    delivery_method = "telegram_cache"
    if version.telegram_file_id:
        document = version.telegram_file_id
    else:
        delivery_method = "s3_upload"
        suffix = f".{bundle.release_file.file_kind}"
        temporary = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        temporary.close()
        temp_path = Path(temporary.name)
        storage = S3Storage(settings)
        await asyncio.to_thread(storage.download_file, version.object_key, temp_path)
        document = FSInputFile(temp_path, filename=version.original_filename)

    status = "sent"
    try:
        try:
            sent = await bot.send_document(
                chat_id=chat_id,
                document=document,
                caption=caption,
                protect_content=True,
            )
        except TelegramBadRequest:
            if not version.telegram_file_id:
                raise
            delivery_method = "s3_upload"
            suffix = f".{bundle.release_file.file_kind}"
            temporary = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            temporary.close()
            temp_path = Path(temporary.name)
            storage = S3Storage(settings)
            await asyncio.to_thread(storage.download_file, version.object_key, temp_path)
            sent = await bot.send_document(
                chat_id=chat_id,
                document=FSInputFile(temp_path, filename=version.original_filename),
                caption=caption,
                protect_content=True,
            )
        if sent.document is not None and sent.document.file_id != version.telegram_file_id:
            async with SessionFactory() as session:
                await CatalogService(session).update_telegram_file_cache(
                    version_id=version.id,
                    telegram_file_id=sent.document.file_id,
                    telegram_file_unique_id=sent.document.file_unique_id,
                )
    except Exception:
        status = "failed"
        raise
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        async with SessionFactory() as session:
            await CatalogService(session).record_download(
                user_id=user_id,
                release_id=release.id,
                file_version_id=version.id,
                delivery_method=delivery_method,
                status=status,
            )


async def _send_search_results(message: Message, query: str) -> None:
    normalized = " ".join(query.split())[:100]
    if len(normalized) < 2:
        await message.answer(
            "🔎 <b>SEARCH TITLES</b>\n\nType at least two characters. You can also use <code>/search title name</code>.",
            reply_markup=search_prompt_keyboard(),
        )
        return
    async with SessionFactory() as session:
        titles = await CatalogService(session).search_titles(normalized)
    text = (
        "🔎 <b>SEARCH RESULTS</b>\n\n"
        f"Results for: <b>{escape(normalized)}</b>"
    )
    if not titles:
        text += f"\n\n{NO_SEARCH_RESULTS}"
    await message.answer(text, reply_markup=search_results_keyboard(titles))


async def _start_search_message(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchTitleState.query)
    await message.answer(
        "🔎 <b>SEARCH TITLES</b>\n\nSend an English title, original title or alias.\n\nTip: use <code>/search Solo Leveling</code> to search in one step.",
        reply_markup=search_prompt_keyboard(),
    )


def create_catalog_router(settings: Settings) -> Router:
    router = Router(name="catalog")

    @router.message(Command("search"))
    async def search_command(
        message: Message, state: FSMContext, command: CommandObject
    ) -> None:
        query = (command.args or "").strip()
        await state.clear()
        if query:
            await _send_search_results(message, query)
            return
        await _start_search_message(message, state)

    @router.message(F.text == NAV_SEARCH)
    async def search_navigation(message: Message, state: FSMContext) -> None:
        await state.clear()
        await _start_search_message(message, state)

    @router.callback_query(F.data.startswith("catalog:list:"))
    async def list_titles(callback: CallbackQuery) -> None:
        page = int((callback.data or "0").rsplit(":", maxsplit=1)[-1])
        await _show_catalogue(callback, settings, max(page, 0))

    @router.callback_query(F.data.startswith("catalog:latest:"))
    async def latest(callback: CallbackQuery) -> None:
        page = int((callback.data or "0").rsplit(":", maxsplit=1)[-1])
        await _show_latest(callback, settings, max(page, 0))

    @router.callback_query(F.data.startswith("catalog:title:"))
    async def title_page(callback: CallbackQuery, db_user: User) -> None:
        title_id = _parse_uuid((callback.data or "").rsplit(":", maxsplit=1)[-1])
        if title_id is None:
            await callback.answer("Invalid title.", show_alert=True)
            return
        await _show_title_by_id(callback, title_id, db_user)

    @router.callback_query(F.data.startswith("catalog:release:"))
    async def release_page(callback: CallbackQuery, db_user: User) -> None:
        release_id = _parse_uuid((callback.data or "").rsplit(":", maxsplit=1)[-1])
        if release_id is None:
            await callback.answer("Invalid release.", show_alert=True)
            return
        await _show_release_by_id(callback, release_id, db_user, settings)

    @router.callback_query(F.data.startswith("catalog:follow:"))
    async def follow(callback: CallbackQuery, db_user: User) -> None:
        title_id = _parse_uuid((callback.data or "").rsplit(":", maxsplit=1)[-1])
        if title_id is None:
            await callback.answer("Invalid title.", show_alert=True)
            return
        async with SessionFactory() as session:
            enabled = await CatalogService(session).toggle_follow(db_user.id, title_id)
        await callback.answer("Title followed." if enabled else "Title unfollowed.")
        await _show_title_by_id(callback, title_id, db_user, answer_callback=False)

    @router.callback_query(F.data == "catalog:library")
    async def library(callback: CallbackQuery, db_user: User) -> None:
        async with SessionFactory() as session:
            titles = await CatalogService(session).followed_titles(db_user.id)
        text = "📖 <b>MY LIBRARY</b>\n\nYour followed titles are shown below."
        if not titles:
            text += "\n\nYou are not following any titles yet."
        await _edit_or_answer(callback, text, library_keyboard(titles))

    @router.callback_query(F.data == "catalog:search")
    async def start_search(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(SearchTitleState.query)
        await _edit_or_answer(
            callback,
            "🔎 <b>SEARCH TITLES</b>\n\nSend an English title, original title or alias.\n\nTip: use <code>/search title name</code> to search in one step.",
            search_prompt_keyboard(),
        )

    @router.callback_query(F.data == "catalog:search:cancel")
    async def cancel_search(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await _edit_or_answer(
            callback,
            "Search cancelled. Choose another action.",
            home_keyboard(),
        )

    @router.message(SearchTitleState.query)
    async def search(message: Message, state: FSMContext) -> None:
        query = (message.text or "").strip()
        if len(" ".join(query.split())) < 2:
            await message.answer(
                "Please send at least two characters, or use <code>/cancel</code>.",
                reply_markup=search_prompt_keyboard(),
            )
            return
        await state.clear()
        await _send_search_results(message, query)

    @router.callback_query(F.data.startswith("catalog:download:"))
    async def download_release(callback: CallbackQuery, db_user: User, bot: Bot) -> None:
        release_id = _parse_uuid((callback.data or "").rsplit(":", maxsplit=1)[-1])
        if release_id is None:
            await callback.answer("Invalid release.", show_alert=True)
            return
        async with SessionFactory() as session:
            service = CatalogService(session)
            release = await service.get_release(release_id, published_only=True)
            if release is None:
                await callback.answer("Release not found.", show_alert=True)
                return
            if not await service.can_download_directly(db_user, settings.admin_telegram_id):
                await callback.answer("An active Boosty membership is required.", show_alert=True)
                return
            title = await service.title_for_release(release)
            files = await service.get_current_file_versions(release.id)
        if {item.release_file.file_kind for item in files} != {"pdf", "epub"}:
            await callback.answer("Release files are incomplete.", show_alert=True)
            return
        await callback.answer("Preparing PDF and EPUB…")
        if callback.from_user is None:
            return
        try:
            for bundle in sorted(
                files, key=lambda item: 0 if item.release_file.file_kind == "pdf" else 1
            ):
                await _send_file_bundle(
                    bot=bot,
                    chat_id=callback.from_user.id,
                    user_id=db_user.id,
                    bundle=bundle,
                    release=release,
                    title=title,
                    settings=settings,
                )
        except Exception:
            await bot.send_message(
                callback.from_user.id,
                "One of the files could not be delivered. Please use Report a Problem once reports are enabled.",
            )

    return router
