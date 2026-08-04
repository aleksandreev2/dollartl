import asyncio
import logging
import signal

from redis.asyncio import Redis
from sqlalchemy import text

from dollartl.bot.dispatcher import create_bot
from dollartl.config import get_settings
from dollartl.db.session import engine
from dollartl.logging import configure_logging
from dollartl.worker.boosty import (
    deliver_next_access_event,
    expire_grace_periods,
    process_pending_verifications,
    synchronize_memberships,
)
from dollartl.worker.publications import process_next_publication

logger = logging.getLogger(__name__)
settings = get_settings()


async def health_tick(redis: Redis[str]) -> None:
    await redis.set("dollartl:worker:last_seen", "ok", ex=120)
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def run() -> None:
    configure_logging(settings.log_level)
    redis: Redis[str] = Redis.from_url(settings.redis_url, decode_responses=True)
    bot = create_bot(settings)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    next_verification = 0.0
    next_membership_sync = 0.0
    next_grace_expiry = 0.0
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    logger.info("worker_started")
    try:
        while not stop.is_set():
            processed = False
            try:
                await health_tick(redis)
                processed = await process_next_publication(bot, settings)
                processed = await deliver_next_access_event(bot, settings) or processed
                now = loop.time()
                if settings.boosty_enabled and now >= next_verification:
                    processed = await process_pending_verifications(settings) or processed
                    next_verification = now + settings.boosty_verification_poll_seconds
                if settings.boosty_enabled and now >= next_membership_sync:
                    processed = await synchronize_memberships(settings) or processed
                    next_membership_sync = now + settings.boosty_membership_sync_seconds
                if now >= next_grace_expiry:
                    processed = bool(await expire_grace_periods(settings)) or processed
                    next_grace_expiry = now + 60
            except Exception:
                logger.exception("worker_tick_failed")
            timeout = 0.2 if processed else settings.worker_poll_seconds
            try:
                await asyncio.wait_for(stop.wait(), timeout=timeout)
            except TimeoutError:
                continue
    finally:
        await bot.session.close()
        await redis.aclose()
        await engine.dispose()
        logger.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(run())
