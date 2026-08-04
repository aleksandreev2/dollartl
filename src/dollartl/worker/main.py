import asyncio
import logging
import signal

from redis.asyncio import Redis
from sqlalchemy import text

from dollartl.bot.dispatcher import create_bot
from dollartl.config import get_settings
from dollartl.db.session import engine
from dollartl.logging import configure_logging
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
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    logger.info("worker_started")
    try:
        while not stop.is_set():
            try:
                await health_tick(redis)
                processed = await process_next_publication(bot, settings)
            except Exception:
                logger.exception("worker_tick_failed")
                processed = False
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
