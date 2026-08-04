from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory
from redis.asyncio import Redis
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert

from dollartl.config import Settings
from dollartl.db.resilience_models import ServiceHeartbeat, TelegramUpdateReceipt
from dollartl.db.session import SessionFactory, engine
from dollartl.storage import S3Storage


@dataclass(frozen=True, slots=True)
class MigrationStatus:
    current: tuple[str, ...]
    expected: tuple[str, ...]

    @property
    def matches(self) -> bool:
        return set(self.current) == set(self.expected)


def expected_migration_heads() -> tuple[str, ...]:
    config_path = Path("alembic.ini")
    if not config_path.exists():
        raise RuntimeError("alembic.ini is missing")
    configuration = Config(str(config_path))
    return tuple(sorted(ScriptDirectory.from_config(configuration).get_heads()))


async def migration_status() -> MigrationStatus:
    expected = await asyncio.to_thread(expected_migration_heads)
    async with engine.connect() as connection:
        rows = await connection.execute(text("SELECT version_num FROM alembic_version"))
        current = tuple(sorted(str(row[0]) for row in rows))
    return MigrationStatus(current=current, expected=expected)


async def record_heartbeat(
    *,
    service_name: str,
    instance_id: str,
    status: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    async with SessionFactory() as session:
        statement = (
            insert(ServiceHeartbeat)
            .values(
                id=uuid4(),
                service_name=service_name,
                instance_id=instance_id,
                status=status,
                last_seen_at=now,
                metadata=metadata or {},
            )
            .on_conflict_do_update(
                constraint="uq_service_heartbeats_service_instance",
                set_={
                    "status": status,
                    "last_seen_at": now,
                    "metadata": metadata or {},
                    "updated_at": now,
                },
            )
        )
        await session.execute(statement)
        await session.commit()


async def service_snapshot(settings: Settings) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=settings.worker_stale_seconds)
    async with SessionFactory() as session:
        heartbeats = list(
            (
                await session.execute(
                    select(ServiceHeartbeat).order_by(
                        ServiceHeartbeat.service_name,
                        ServiceHeartbeat.last_seen_at.desc(),
                    )
                )
            ).scalars()
        )
    services = [
        {
            "service_name": item.service_name,
            "instance_id": item.instance_id,
            "status": item.status,
            "last_seen_at": item.last_seen_at.isoformat(),
            "stale": item.last_seen_at < cutoff,
            "metadata": item.metadata_json,
        }
        for item in heartbeats
    ]
    return {"services": services, "worker_stale_after_seconds": settings.worker_stale_seconds}


async def dependency_snapshot(settings: Settings) -> dict[str, Any]:
    result: dict[str, Any] = {}
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        result["database"] = {"ok": True}
    except Exception as exc:
        result["database"] = {"ok": False, "error": type(exc).__name__}

    try:
        migration = await migration_status()
        result["migrations"] = {
            "ok": migration.matches,
            "current": list(migration.current),
            "expected": list(migration.expected),
        }
    except Exception as exc:
        result["migrations"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    redis: Redis[str] = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        result["redis"] = {"ok": bool(await redis.ping())}
    except Exception as exc:
        result["redis"] = {"ok": False, "error": type(exc).__name__}
    finally:
        await redis.aclose()

    try:
        await asyncio.to_thread(S3Storage(settings).ensure_bucket_access)
        result["primary_storage"] = {"ok": True, "bucket": settings.s3_bucket}
    except Exception as exc:
        result["primary_storage"] = {"ok": False, "error": type(exc).__name__}

    if settings.backup_enabled:
        try:
            await asyncio.to_thread(S3Storage.backup(settings).ensure_bucket_access)
            result["backup_storage"] = {"ok": True, "bucket": settings.s3_backup_bucket}
        except Exception as exc:
            result["backup_storage"] = {"ok": False, "error": type(exc).__name__}
    else:
        result["backup_storage"] = {"ok": True, "enabled": False}
    return result


async def prune_resilience_records(settings: Settings) -> dict[str, int]:
    receipt_cutoff = datetime.now(timezone.utc) - timedelta(days=settings.webhook_receipt_retention_days)
    heartbeat_cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    async with SessionFactory() as session:
        receipts = await session.execute(
            delete(TelegramUpdateReceipt).where(
                TelegramUpdateReceipt.updated_at < receipt_cutoff,
                TelegramUpdateReceipt.status.in_(["completed", "failed"]),
            )
        )
        heartbeats = await session.execute(
            delete(ServiceHeartbeat).where(ServiceHeartbeat.last_seen_at < heartbeat_cutoff)
        )
        await session.commit()
        return {
            "telegram_update_receipts": int(receipts.rowcount or 0),
            "service_heartbeats": int(heartbeats.rowcount or 0),
        }
