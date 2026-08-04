from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from dollartl.bot.admin import create_admin_router
from dollartl.bot.handlers import create_user_router
from dollartl.bot.middleware import AccessMiddleware
from dollartl.config import Settings


def create_bot(settings: Settings) -> Bot:
    token = settings.telegram_bot_token.get_secret_value()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    return Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def create_dispatcher(settings: Settings) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.update.outer_middleware(AccessMiddleware(settings))
    dispatcher.include_router(create_admin_router(settings))
    dispatcher.include_router(create_user_router(settings))
    return dispatcher
