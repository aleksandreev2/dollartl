from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from dollartl.admin.people_common import Admin
from dollartl.db.admin_models import Broadcast, BroadcastRecipient
from dollartl.db.models import AuditLog
from dollartl.db.session import SessionFactory

router = APIRouter(tags=["admin-broadcasts"])


class BroadcastRetryBatchRequest(BaseModel):
    broadcast_ids: list[UUID] = Field(min_length=1, max_length=200)
    dry_run: bool = True
    idempotency_key: str = Field(min_length=12, max_length=180)


async def _preview(
    session,
    ids: list[UUID],
    *,
    lock: bool = False,
) -> tuple[dict[str, Any], list[tuple[Broadcast, list[BroadcastRecipient]]]]:
    statement = select(Broadcast).where(
        Broadcast.id.in_(ids),
        Broadcast.status == "failed",
    )
    if lock:
        statement = statement.with_for_update()
    broadcasts = list((await session.execute(statement)).scalars())
    rows: list[tuple[Broadcast, list[BroadcastRecipient]]] = []
    items: list[dict[str, Any]] = []
    for broadcast in broadcasts:
        recipient_statement = select(BroadcastRecipient).where(
            BroadcastRecipient.broadcast_id == broadcast.id,
            BroadcastRecipient.status == "failed",
            BroadcastRecipient.attempts < 5,
        )
        if lock:
            recipient_statement = recipient_statement.with_for_update()
        recipients = list((await session.execute(recipient_statement)).scalars())
        rows.append((broadcast, recipients))
        if recipients:
            items.append({"id": str(broadcast.id), "recipients": len(recipients)})
    found_ids = {item.id for item in broadcasts}
    preview = {
        "requested": len(ids),
        "found": len(broadcasts),
        "eligible_broadcasts": len(items),
        "retriable_recipients": sum(item["recipients"] for item in items),
        "missing": len(set(ids) - found_ids),
        "items": items,
    }
    return preview, rows


@router.post("/broadcasts/retry-failed")
async def retry_failed_broadcasts(
    payload: BroadcastRetryBatchRequest,
    admin: Admin,
) -> dict[str, Any]:
    unique_ids = list(dict.fromkeys(payload.broadcast_ids))
    async with SessionFactory() as session:
        preview, _ = await _preview(session, unique_ids)
        if payload.dry_run:
            return {"dry_run": True, "replayed": False, **preview}

        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": payload.idempotency_key},
        )
        existing = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.action == "broadcast_batch.retry_completed",
                    AuditLog.correlation_id == payload.idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {"dry_run": False, "replayed": True, **existing.payload}

        preview, rows = await _preview(session, unique_ids, lock=True)
        now = datetime.now(timezone.utc)
        for broadcast, recipients in rows:
            if not recipients:
                continue
            for recipient in recipients:
                recipient.status = "pending"
                recipient.last_error = None
            broadcast.status = "scheduled"
            broadcast.scheduled_at = now
            broadcast.started_at = None
            broadcast.completed_at = None
            broadcast.last_error = None
            session.add(
                AuditLog(
                    actor_telegram_id=admin.telegram_id,
                    action="broadcast.retry_queued",
                    entity_type="broadcast",
                    entity_id=str(broadcast.id),
                    payload={
                        "recipients": len(recipients),
                        "idempotency_key": payload.idempotency_key,
                    },
                    correlation_id=payload.idempotency_key,
                )
            )

        result = dict(preview)
        session.add(
            AuditLog(
                actor_telegram_id=admin.telegram_id,
                action="broadcast_batch.retry_completed",
                entity_type="broadcast_batch",
                entity_id=payload.idempotency_key,
                payload=result,
                correlation_id=payload.idempotency_key,
            )
        )
        await session.commit()
        return {"dry_run": False, "replayed": False, **result}
