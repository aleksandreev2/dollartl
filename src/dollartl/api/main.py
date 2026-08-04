from contextlib import asynccontextmanager

from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Response, status
from sqlalchemy import text

from dollartl.bot.dispatcher import create_bot, create_dispatcher
from dollartl.config import get_settings
from dollartl.db.session import engine
from dollartl.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
bot = create_bot(settings) if settings.telegram_bot_token.get_secret_value() else None
dispatcher = create_dispatcher(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    if bot is not None:
        await bot.session.close()
    await engine.dispose()


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)


@app.get("/health/live", include_in_schema=False)
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
async def ready(response: Response) -> dict[str, str]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "database": type(exc).__name__}
    return {"status": "ready", "database": "ok"}


@app.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(
    update: Update,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    if settings.maintenance_mode:
        raise HTTPException(status_code=503, detail="Maintenance mode")
    expected = settings.telegram_webhook_secret.get_secret_value()
    if expected and x_telegram_bot_api_secret_token != expected:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    if bot is None:
        raise HTTPException(status_code=503, detail="Telegram bot is not configured")
    await dispatcher.feed_update(bot, update)
    return {"ok": True}
