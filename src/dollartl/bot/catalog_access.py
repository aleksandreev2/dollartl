from __future__ import annotations

from uuid import UUID

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from dollartl.bot.keyboards import title_keyboard
from dollartl.bot.texts import NO_RELEASES, render_title
from dollartl.config import Settings
from dollartl.db.models import User
from dollartl.db.session import SessionFactory
from dollartl.services.catalog import CatalogService
from dollartl.services.community import CommunityService


def _uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


async def _render_access_aware_title(
    callback: CallbackQuery,
    title_id: UUID,
    db_user: User,
    settings: Settings,
    *,
    answer_callback: bool,
) -> bool | None:
    async with SessionFactory() as session:
        catalog = CatalogService(session)
        title = await catalog.get_title(title_id, published_only=True)
        if title is None:
            await callback.answer("Novel not found.", show_alert=True)
            return None
        releases = await catalog.list_releases(title.id)
        followed = await catalog.is_following(db_user.id, title.id)
        thanked = await CommunityService(session, settings).has_download_thanks(db_user.id)
        direct_download = await catalog.can_download_directly(
            db_user, settings.admin_telegram_id
        )

    text = render_title(title)
    if not releases:
        text += f"\n\n{NO_RELEASES}"
    markup = title_keyboard(
        title,
        releases,
        followed=followed,
        thanked=thanked,
        direct_download=direct_download,
    )

    if answer_callback:
        await callback.answer()
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(text, reply_markup=markup)
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                raise
    return direct_download


def create_catalog_access_router(settings: Settings) -> Router:
    """Render novel cards with the current thank-you and download access state.

    This router is registered before the legacy catalogue router so every normal
    novel navigation path gets an access-aware keyboard without changing the
    release delivery and catalogue listing handlers.
    """

    router = Router(name="catalog-access")

    @router.callback_query(F.data.startswith("catalog:title:"))
    async def title_page(callback: CallbackQuery, db_user: User) -> None:
        title_id = _uuid((callback.data or "").rsplit(":", maxsplit=1)[-1])
        if title_id is None:
            await callback.answer("Invalid novel.", show_alert=True)
            return
        await _render_access_aware_title(
            callback,
            title_id,
            db_user,
            settings,
            answer_callback=True,
        )

    @router.callback_query(F.data.startswith("catalog:follow:"))
    async def follow_novel(callback: CallbackQuery, db_user: User) -> None:
        title_id = _uuid((callback.data or "").rsplit(":", maxsplit=1)[-1])
        if title_id is None:
            await callback.answer("Invalid novel.", show_alert=True)
            return
        async with SessionFactory() as session:
            enabled = await CatalogService(session).toggle_follow(db_user.id, title_id)
        await callback.answer("Novel followed." if enabled else "Novel unfollowed.")
        await _render_access_aware_title(
            callback,
            title_id,
            db_user,
            settings,
            answer_callback=False,
        )

    @router.callback_query(F.data.startswith("community:thanks:"))
    async def record_thanks(callback: CallbackQuery, db_user: User) -> None:
        title_id = _uuid((callback.data or "").rsplit(":", maxsplit=1)[-1])
        if title_id is None:
            await callback.answer("Invalid novel.", show_alert=True)
            return
        async with SessionFactory() as session:
            created = await CommunityService(session, settings).record_download_thanks(
                db_user.id
            )
        direct_download = await _render_access_aware_title(
            callback,
            title_id,
            db_user,
            settings,
            answer_callback=False,
        )
        if direct_download is None:
            return
        if direct_download:
            text = (
                "Thank you. Download buttons are now available."
                if created
                else "Download buttons refreshed."
            )
        else:
            text = (
                "Thank you recorded. Link an active Boosty membership to download."
                if created
                else "Thank you is already recorded. Active Boosty access is still required."
            )
        await callback.answer(text, show_alert=True)

    return router
