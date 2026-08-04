from __future__ import annotations

from uuid import uuid4

from redis.asyncio import Redis

from dollartl.config import get_settings
from dollartl.resilience.leader import RedisLeaderLease


async def test_redis_leader_lease_handoff() -> None:
    settings = get_settings()
    redis: Redis[str] = Redis.from_url(settings.redis_url, decode_responses=True)
    key = f"dollartl:test:leader:{uuid4().hex}"
    first = RedisLeaderLease(redis=redis, key=key, ttl_seconds=10)
    second = RedisLeaderLease(redis=redis, key=key, ttl_seconds=10)
    try:
        assert await first.acquire() is True
        assert await second.acquire() is False
        assert await first.renew() is True

        await first.release()
        assert await second.acquire() is True
        assert await second.renew() is True
    finally:
        await first.release()
        await second.release()
        await redis.delete(key)
        await redis.aclose()
