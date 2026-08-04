import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from dollartl.admin.raw_router import router as raw_admin_router
from dollartl.admin.resilience_router import router as resilience_admin_router
from dollartl.admin.router import router as admin_router
from dollartl.bot.dispatcher import create_bot, create_dispatcher
from dollartl.config import get_settings
from dollartl.db.session import engine
from dollartl.logging import configure_logging
from dollartl.resilience.health import migration_status, record_heartbeat
from dollartl.resilience.webhook import claim_update, complete_update, fail_update

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)
bot = create_bot(settings) if settings.telegram_bot_token.get_secret_value() else None
dispatcher = create_dispatcher(settings)


def api_instance_id() -> str:
    return (
        os.getenv("RAILWAY_REPLICA_ID")
        or os.getenv("RAILWAY_SERVICE_ID")
        or os.getenv("HOSTNAME")
        or uuid4().hex
    )[:120]


async def api_heartbeat(stop: asyncio.Event, instance_id: str) -> None:
    while not stop.is_set():
        try:
            await record_heartbeat(
                service_name="api",
                instance_id=instance_id,
                status="healthy",
                metadata={"maintenance_mode": settings.maintenance_mode},
            )
        except Exception:
            logger.exception("api_heartbeat_failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.worker_heartbeat_seconds)
        except TimeoutError:
            continue


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    stop = asyncio.Event()
    instance_id = api_instance_id()
    heartbeat_task = asyncio.create_task(api_heartbeat(stop, instance_id))
    try:
        yield
    finally:
        stop.set()
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)
        try:
            await record_heartbeat(
                service_name="api",
                instance_id=instance_id,
                status="stopping",
                metadata={"maintenance_mode": settings.maintenance_mode},
            )
        except Exception:
            logger.exception("api_final_heartbeat_failed")
        if bot is not None:
            await bot.session.close()
        await engine.dispose()


app = FastAPI(title=settings.app_name, version="0.8.0", lifespan=lifespan)
allowed_origins = [settings.admin_web_origin.rstrip("/")]
if settings.app_env == "development":
    allowed_origins.extend(["http://localhost:8080", "http://localhost:5173"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(allowed_origins)),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Telegram-Init-Data", "X-Admin-Development-Id"],
)
app.include_router(admin_router)
app.include_router(raw_admin_router)
app.include_router(resilience_admin_router)


@app.get("/health/live", include_in_schema=False)
async def live() -> dict[str, str]:
    return {"status": "ok", "version": "0.8.0"}


@app.get("/health/ready", include_in_schema=False)
async def ready(response: Response) -> dict[str, object]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        migrations = await migration_status()
    except Exception as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "error": f"{type(exc).__name__}: {exc}",
        }
    if not migrations.matches:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "database": "ok",
            "migrations": {
                "current": list(migrations.current),
                "expected": list(migrations.expected),
            },
        }
    return {
        "status": "ready",
        "database": "ok",
        "migrations": list(migrations.current),
    }


@app.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(
    update: Update,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    if settings.maintenance_mode:
        raise HTTPException(status_code=503, detail="Maintenance mode")
    expected = settings.telegram_webhook_secret.get_secret_value()
    if settings.app_env == "production" and not expected:
        raise HTTPException(status_code=503, detail="Webhook secret is not configured")
    if expected and x_telegram_bot_api_secret_token != expected:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    if bot is None:
        raise HTTPException(status_code=503, detail="Telegram bot is not configured")
    claimed = await claim_update(update.update_id, settings)
    if not claimed:
        return {"ok": True, "duplicate": True}
    try:
        await dispatcher.feed_update(bot, update)
    except Exception as exc:
        await fail_update(update.update_id, exc)
        raise
    await complete_update(update.update_id)
    return {"ok": True, "duplicate": False}
