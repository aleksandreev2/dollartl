import asyncio
import logging
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from dollartl.admin.raw_router import router as raw_admin_router
from dollartl.admin.resilience_router import router as resilience_admin_router
from dollartl.admin.router import router as admin_router
from dollartl.admin.version_router import router as version_admin_router
from dollartl.admin.workbench_router import router as workbench_admin_router
from dollartl.api.bootstrap import configure_telegram_webhook, verify_storage
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
admin_web_dir = Path(os.getenv("ADMIN_WEB_DIR", "/app/admin-web-dist"))
admin_web_verified = False
storage_verified = False
telegram_verified = False
_ADMIN_ASSET_RE = re.compile(r"(?:src|href)=[\"'](/admin/assets/[^\"'?#]+)[\"']")


def api_instance_id() -> str:
    return (
        os.getenv("RAILWAY_REPLICA_ID")
        or os.getenv("RAILWAY_SERVICE_ID")
        or os.getenv("HOSTNAME")
        or uuid4().hex
    )[:120]


async def verify_admin_web(app: FastAPI) -> None:
    global admin_web_verified

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://startup.local") as client:
        index_response = await client.get("/admin/")
        index_response.raise_for_status()
        content_type = index_response.headers.get("content-type", "")
        if not content_type.startswith("text/html"):
            raise RuntimeError(
                f"Embedded admin index returned unexpected content type: {content_type}"
            )

        asset_paths = sorted(set(_ADMIN_ASSET_RE.findall(index_response.text)))
        if not asset_paths:
            raise RuntimeError("Embedded admin index does not reference built assets")

        for asset_path in asset_paths:
            asset_response = await client.get(asset_path)
            asset_response.raise_for_status()
            if not asset_response.content:
                raise RuntimeError(f"Embedded admin asset is empty: {asset_path}")
            asset_content_type = asset_response.headers.get("content-type", "")
            if asset_path.endswith(".css") and not asset_content_type.startswith("text/css"):
                raise RuntimeError(
                    f"Embedded CSS asset has unexpected content type: {asset_content_type}"
                )
            if asset_path.endswith(".js") and "javascript" not in asset_content_type:
                raise RuntimeError(
                    f"Embedded JavaScript asset has unexpected content type: "
                    f"{asset_content_type}"
                )

    admin_web_verified = True
    logger.info(
        "admin_web_self_check_ok",
        extra={"asset_count": len(asset_paths), "path": str(admin_web_dir)},
    )


async def verify_production_dependencies(app: FastAPI) -> None:
    global storage_verified, telegram_verified

    await verify_admin_web(app)
    await verify_storage(settings)
    storage_verified = True

    if bot is None:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required in production")
    await configure_telegram_webhook(bot, dispatcher, settings)
    telegram_verified = True


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
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.app_env == "production":
        await verify_production_dependencies(app)

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
app.include_router(version_admin_router)
app.include_router(admin_router)
app.include_router(raw_admin_router)
app.include_router(resilience_admin_router)
app.include_router(workbench_admin_router)


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

    production_checks_ok = admin_web_verified and storage_verified and telegram_verified
    if not migrations.matches or (
        settings.app_env == "production" and not production_checks_ok
    ):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "database": "ok",
            "admin_web": "ok" if admin_web_verified else "not_ready",
            "storage": "ok" if storage_verified else "not_ready",
            "telegram": "ok" if telegram_verified else "not_ready",
            "migrations": {
                "current": list(migrations.current),
                "expected": list(migrations.expected),
            },
        }
    return {
        "status": "ready",
        "database": "ok",
        "admin_web": "ok" if admin_web_verified else "not_checked",
        "storage": "ok" if storage_verified else "not_checked",
        "telegram": "ok" if telegram_verified else "not_checked",
        "maintenance_mode": settings.maintenance_mode,
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


if admin_web_dir.is_dir():
    app.mount(
        "/admin",
        StaticFiles(directory=admin_web_dir, html=True),
        name="admin-web",
    )
else:
    logger.warning("admin_web_assets_missing", extra={"path": str(admin_web_dir)})
