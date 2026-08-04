from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from dollartl.config import Settings
from dollartl.storage import S3Storage

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StorageBootstrapResult:
    bucket: str
    size: int


@dataclass(frozen=True, slots=True)
class TelegramBootstrapResult:
    username: str
    webhook_url: str
    pending_update_count: int


async def verify_storage(settings: Settings) -> StorageBootstrapResult:
    storage = S3Storage(settings)
    key = f"healthchecks/startup/{uuid4().hex}.bin"
    payload = f"dollartl-storage-check:{uuid4().hex}".encode()
    round_trip_complete = False

    try:
        await asyncio.to_thread(storage.ensure_bucket_access)
        uploaded = await asyncio.to_thread(
            storage.upload_fileobj,
            BytesIO(payload),
            key,
            "application/octet-stream",
        )
        if uploaded.size != len(payload):
            raise RuntimeError(
                f"S3 startup upload size mismatch: expected {len(payload)}, got {uploaded.size}"
            )

        with TemporaryDirectory(prefix="dollartl-storage-check-") as directory:
            destination = Path(directory) / "download.bin"
            await asyncio.to_thread(storage.download_file, key, destination)
            downloaded = await asyncio.to_thread(destination.read_bytes)
        if downloaded != payload:
            raise RuntimeError("S3 startup download does not match uploaded payload")
        round_trip_complete = True
    finally:
        try:
            await asyncio.to_thread(storage.delete, key)
        except Exception:
            if round_trip_complete:
                raise
            logger.exception("storage_self_check_cleanup_failed", extra={"key": key})

    result = StorageBootstrapResult(bucket=storage.bucket, size=len(payload))
    logger.info(
        "storage_self_check_ok",
        extra={"bucket": result.bucket, "size": result.size},
    )
    return result


async def configure_telegram_webhook(
    bot: Bot,
    dispatcher: Dispatcher,
    settings: Settings,
) -> TelegramBootstrapResult:
    webhook_url = settings.webhook_url
    secret = settings.telegram_webhook_secret.get_secret_value()
    if not settings.telegram_webhook_base_url.strip():
        raise RuntimeError("TELEGRAM_WEBHOOK_BASE_URL is required in production")
    if not secret:
        raise RuntimeError("TELEGRAM_WEBHOOK_SECRET is required in production")

    identity = await bot.get_me()
    default_commands = [
        BotCommand(command="start", description="Open the home screen"),
        BotCommand(command="latest", description="Show latest releases"),
        BotCommand(command="browse", description="Browse all titles"),
        BotCommand(command="search", description="Search titles: /search name"),
        BotCommand(command="library", description="Open your followed titles"),
        BotCommand(command="menu", description="Open additional actions"),
        BotCommand(command="settings", description="Open settings"),
        BotCommand(command="help", description="Show help"),
        BotCommand(command="cancel", description="Cancel the current action"),
    ]
    await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())
    await bot.set_my_commands(
        [
            *default_commands,
            BotCommand(command="admin", description="Open the admin panel"),
        ],
        scope=BotCommandScopeChat(chat_id=settings.admin_telegram_id),
    )

    allowed_updates = dispatcher.resolve_used_update_types()
    configured = await bot.set_webhook(
        url=webhook_url,
        secret_token=secret,
        allowed_updates=allowed_updates,
        drop_pending_updates=False,
    )
    if not configured:
        raise RuntimeError("Telegram rejected webhook configuration")

    info = await bot.get_webhook_info()
    if info.url.rstrip("/") != webhook_url.rstrip("/"):
        raise RuntimeError(
            f"Telegram webhook URL mismatch: expected {webhook_url}, got {info.url or '<empty>'}"
        )

    username = identity.username or str(identity.id)
    result = TelegramBootstrapResult(
        username=username,
        webhook_url=info.url,
        pending_update_count=info.pending_update_count,
    )
    logger.info(
        "telegram_webhook_self_check_ok",
        extra={
            "bot_username": result.username,
            "pending_update_count": result.pending_update_count,
            "webhook_url": result.webhook_url,
            "allowed_update_count": len(allowed_updates),
            "last_error_message": info.last_error_message,
        },
    )
    return result
