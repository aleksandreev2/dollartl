from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode

from dollartl.bot.admin import create_admin_router
from dollartl.bot.admin_boosty import create_admin_boosty_router
from dollartl.bot.admin_catalog import create_admin_catalog_router
from dollartl.bot.admin_community import create_admin_community_router
from dollartl.bot.admin_suggestions import create_admin_suggestion_router
from dollartl.bot.boosty import create_boosty_router
from dollartl.bot.catalog import create_catalog_router
from dollartl.bot.community import create_community_router
from dollartl.bot.handlers import create_user_router
from dollartl.bot.middleware import AccessMiddleware
from dollartl.bot.navigation import create_navigation_router
from dollartl.bot.suggestions import create_suggestion_router
from dollartl.config import Settings


def create_bot(settings: Settings) -> Bot:
    token = settings.telegram_bot_token.get_secret_value()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    defaults = DefaultBotProperties(parse_mode=ParseMode.HTML)
    if settings.telegram_api_base_url:
        api = TelegramAPIServer.from_base(
            settings.telegram_api_base_url.rstrip("/"),
            is_local=True,
        )
        return Bot(
            token=token,
            session=AiohttpSession(api=api),
            default=defaults,
        )
    return Bot(token=token, default=defaults)


def create_dispatcher(settings: Settings) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.update.outer_middleware(AccessMiddleware(settings))
    dispatcher.include_router(create_navigation_router(settings))
    dispatcher.include_router(create_admin_router(settings))
    dispatcher.include_router(create_admin_catalog_router(settings))
    dispatcher.include_router(create_admin_boosty_router(settings))
    dispatcher.include_router(create_admin_community_router(settings))
    dispatcher.include_router(create_admin_suggestion_router(settings))
    dispatcher.include_router(create_boosty_router(settings))
    dispatcher.include_router(create_community_router(settings))
    dispatcher.include_router(create_suggestion_router(settings))
    dispatcher.include_router(create_catalog_router(settings))
    dispatcher.include_router(create_user_router(settings))
    return dispatcher
