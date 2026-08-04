from __future__ import annotations

from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from dollartl.bot.handlers import home_text
from dollartl.bot.keyboards import (
    NAV_BROWSE,
    NAV_CANCEL,
    NAV_HOME,
    NAV_LATEST,
    NAV_LIBRARY,
    NAV_MENU,
    catalogue_keyboard,
    home_keyboard,
    latest_keyboard,
    library_keyboard,
    persistent_navigation_keyboard,
)
from dollartl.config import Settings
from dollartl.db.models import Title, User
from dollartl.db.session import SessionFactory
from dollartl.services.catalog import CatalogService


async def _show_home(message: Message, db_user: User, settings: Settings) -> None:
    await message.answer(
        await home_text(db_user, settings),
        reply_markup=persistent_navigation_keyboard(),
    )


async def _show_more(message: Message, db_user: User, settings: Settings) -> None:
    await message.answer(
        await home_text(db_user, settings),
        reply_markup=home_keyboard(),
    )


async def _show_catalogue(message: Message, settings: Settings) -> None:
    async with SessionFactory() as session:
        service = CatalogService(session)
        titles = await service.list_titles(page=0, page_size=settings.catalogue_page_size)
        count = await service.count_titles()
    has_next = settings.catalogue_page_size < count
    text = "📚 <b>BROWSE TITLES</b>\n\nChoose a title or search by name."
    if not titles:
        text += "\n\nNo translated titles are available yet."
    await message.answer(
        text,
        reply_markup=catalogue_keyboard(titles, page=0, has_next=has_next),
    )


async def _show_latest(message: Message, settings: Settings) -> None:
    async with SessionFactory() as session:
        service = CatalogService(session)
        releases = await service.latest_releases(
            page=0,
            page_size=settings.catalogue_page_size + 1,
        )
        has_next = len(releases) > settings.catalogue_page_size
        releases = releases[: settings.catalogue_page_size]
        titles: dict[UUID, Title] = {}
        for release in releases:
            titles[release.title_id] = await service.title_for_release(release)
    text = "🆕 <b>LATEST RELEASES</b>\n\nChoose a chapter package."
    if not releases:
        text += "\n\nNo releases have been published yet."
    await message.answer(
        text,
        reply_markup=latest_keyboard(releases, titles, page=0, has_next=has_next),
    )


async def _show_library(message: Message, db_user: User) -> None:
    async with SessionFactory() as session:
        titles = await CatalogService(session).followed_titles(db_user.id)
    text = "📖 <b>MY LIBRARY</b>\n\nYour followed titles are shown below."
    if not titles:
        text += "\n\nYou are not following any titles yet."
    await message.answer(text, reply_markup=library_keyboard(titles))


def create_navigation_router(settings: Settings) -> Router:
    router = Router(name="navigation")

    @router.message(Command("cancel"))
    @router.message(F.text == NAV_CANCEL)
    async def cancel(message: Message, state: FSMContext) -> None:
        active_state = await state.get_state()
        await state.clear()
        text = (
            "✅ Current action cancelled."
            if active_state is not None
            else "There is no active action to cancel."
        )
        await message.answer(text, reply_markup=persistent_navigation_keyboard())

    @router.message(Command("menu"))
    @router.message(F.text == NAV_MENU)
    async def more(message: Message, db_user: User) -> None:
        await _show_more(message, db_user, settings)

    @router.message(F.text == NAV_HOME)
    async def home(message: Message, db_user: User) -> None:
        await _show_home(message, db_user, settings)

    @router.message(Command("browse"))
    @router.message(F.text == NAV_BROWSE)
    async def browse(message: Message) -> None:
        await _show_catalogue(message, settings)

    @router.message(Command("latest"))
    @router.message(F.text == NAV_LATEST)
    async def latest(message: Message) -> None:
        await _show_latest(message, settings)

    @router.message(Command("library"))
    @router.message(F.text == NAV_LIBRARY)
    async def library(message: Message, db_user: User) -> None:
        await _show_library(message, db_user)

    return router
