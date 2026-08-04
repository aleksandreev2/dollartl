import asyncio
import logging
import os
import signal
from uuid import uuid4

from redis.asyncio import Redis

from dollartl.bot.dispatcher import create_bot
from dollartl.config import get_settings
from dollartl.db.session import engine
from dollartl.logging import configure_logging
from dollartl.resilience.backups import process_next_backup
from dollartl.resilience.cleanup import cleanup_temporary_files
from dollartl.resilience.health import prune_resilience_records, record_heartbeat
from dollartl.resilience.leader import RedisLeaderLease
from dollartl.worker.boosty import (
    deliver_next_access_event,
    expire_grace_periods,
    process_pending_verifications,
    synchronize_memberships,
)
from dollartl.worker.broadcasts import process_next_broadcast
from dollartl.worker.publications import process_next_publication

logger = logging.getLogger(__name__)
settings = get_settings()


def instance_id() -> str:
    return (
        os.getenv("RAILWAY_REPLICA_ID")
        or os.getenv("RAILWAY_SERVICE_ID")
        or os.getenv("HOSTNAME")
        or uuid4().hex
    )[:120]


async def lease_keeper(
    lease: RedisLeaderLease,
    stop: asyncio.Event,
) -> None:
    interval = max(1.0, lease.ttl_seconds / 3)
    while not stop.is_set():
        try:
            await lease.ensure()
        except Exception:
            lease.held = False
            logger.exception("worker_leader_lease_failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            continue


async def heartbeat_keeper(
    redis: Redis[str],
    lease: RedisLeaderLease,
    stop: asyncio.Event,
    worker_instance_id: str,
) -> None:
    while not stop.is_set():
        try:
            await redis.set(
                "dollartl:worker:last_seen",
                worker_instance_id,
                ex=max(settings.worker_stale_seconds, 60),
            )
            await record_heartbeat(
                service_name="worker",
                instance_id=worker_instance_id,
                status="healthy" if lease.held else "degraded",
                metadata={"leader": lease.held},
            )
        except Exception:
            logger.exception("worker_heartbeat_failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.worker_heartbeat_seconds)
        except TimeoutError:
            continue


async def run() -> None:
    configure_logging(settings.log_level)
    redis: Redis[str] = Redis.from_url(settings.redis_url, decode_responses=True)
    bot = create_bot(settings)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    worker_instance_id = instance_id()
    lease = RedisLeaderLease(
        redis=redis,
        key="dollartl:worker:leader",
        ttl_seconds=settings.worker_leader_lock_seconds,
    )
    next_verification = 0.0
    next_membership_sync = 0.0
    next_grace_expiry = 0.0
    next_backup = 0.0
    next_cleanup = 0.0

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    lease_task = asyncio.create_task(lease_keeper(lease, stop))
    heartbeat_task = asyncio.create_task(
        heartbeat_keeper(redis, lease, stop, worker_instance_id)
    )
    logger.info("worker_started", extra={"instance_id": worker_instance_id})
    try:
        while not stop.is_set():
            if not lease.held:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_seconds)
                except TimeoutError:
                    continue
                continue

            processed = False
            try:
                processed = await process_next_publication(bot, settings)
                processed = await process_next_broadcast(bot, settings) or processed
                processed = await deliver_next_access_event(bot, settings) or processed
                now = loop.time()

                if now >= next_backup:
                    processed = await process_next_backup(bot, settings) or processed
                    next_backup = now + settings.backup_poll_seconds

                if settings.boosty_enabled and now >= next_verification:
                    processed = await process_pending_verifications(settings) or processed
                    next_verification = now + settings.boosty_verification_poll_seconds
                if settings.boosty_enabled and now >= next_membership_sync:
                    processed = await synchronize_memberships(settings) or processed
                    next_membership_sync = now + settings.boosty_membership_sync_seconds
                if now >= next_grace_expiry:
                    processed = bool(await expire_grace_periods(settings)) or processed
                    next_grace_expiry = now + 60
                if now >= next_cleanup:
                    cleanup = await cleanup_temporary_files(settings)
                    pruned = await prune_resilience_records(settings)
                    logger.info(
                        "resilience_cleanup_completed",
                        extra={"temporary": cleanup, "database": pruned},
                    )
                    next_cleanup = now + settings.cleanup_interval_seconds
            except Exception:
                logger.exception("worker_tick_failed")

            try:
                await asyncio.wait_for(
                    stop.wait(),
                    timeout=0.2 if processed else settings.worker_poll_seconds,
                )
            except TimeoutError:
                continue
    finally:
        stop.set()
        for task in (lease_task, heartbeat_task):
            task.cancel()
        await asyncio.gather(lease_task, heartbeat_task, return_exceptions=True)
        try:
            await record_heartbeat(
                service_name="worker",
                instance_id=worker_instance_id,
                status="stopping",
                metadata={"leader": lease.held},
            )
        except Exception:
            logger.exception("worker_final_heartbeat_failed")
        try:
            await lease.release()
        except Exception:
            logger.exception("worker_lease_release_failed")
        await bot.session.close()
        await redis.aclose()
        await engine.dispose()
        logger.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(run())
