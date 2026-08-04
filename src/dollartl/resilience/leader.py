from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from redis.asyncio import Redis

_RENEW_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('expire', KEYS[1], ARGV[2])
else
  return 0
end
"""

_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
else
  return 0
end
"""


@dataclass(slots=True)
class RedisLeaderLease:
    redis: Redis[str]
    key: str
    ttl_seconds: int
    token: str = field(default_factory=lambda: uuid4().hex)
    held: bool = False

    async def acquire(self) -> bool:
        acquired = await self.redis.set(
            self.key,
            self.token,
            ex=self.ttl_seconds,
            nx=True,
        )
        self.held = bool(acquired)
        return self.held

    async def renew(self) -> bool:
        if not self.held:
            return False
        renewed = await self.redis.eval(
            _RENEW_SCRIPT,
            1,
            self.key,
            self.token,
            str(self.ttl_seconds),
        )
        self.held = bool(renewed)
        return self.held

    async def ensure(self) -> bool:
        if self.held and await self.renew():
            return True
        return await self.acquire()

    async def release(self) -> None:
        if self.held:
            await self.redis.eval(_RELEASE_SCRIPT, 1, self.key, self.token)
        self.held = False
