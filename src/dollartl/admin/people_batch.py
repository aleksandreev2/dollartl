from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select, text

from dollartl.admin.people_common import Admin, BatchModerationRequest
from dollartl.db.community_models import (
    Comment,
    Report,
    TranslationRating,
    TranslationRatingStatusHistory,
)
from dollartl.db.models import AuditLog
from dollartl.db.session import SessionFactory

router = APIRouter()


@router.post("/moderation/batch")
async def moderation_batch(
    payload: BatchModerationRequest,
    admin: Admin,
) -> dict[str, Any]:
    async with SessionFactory() as session:
        comment_rows: list[Comment] = []
        rating_rows: list[TranslationRating] = []
        report_rows: list[Report] = []
        if payload.kind == "comments":
            comment_rows = list(
                (
                    await session.execute(
                        select(Comment).where(Comment.id.in_(payload.ids))
                    )
                ).scalars()
            )
            found_ids = {item.id for item in comment_rows}
        elif payload.kind == "ratings":
            rating_rows = list(
                (
                    await session.execute(
                        select(TranslationRating).where(
                            TranslationRating.id.in_(payload.ids)
                        )
                    )
                ).scalars()
            )
            found_ids = {item.id for item in rating_rows}
        else:
            report_rows = list(
                (
                    await session.execute(
                        select(Report).where(Report.id.in_(payload.ids))
                    )
                ).scalars()
            )
            found_ids = {item.id for item in report_rows}

        preview = {
            "kind": payload.kind,
            "action": payload.action,
            "requested": len(payload.ids),
            "found": len(found_ids),
            "missing": len(set(payload.ids) - found_ids),
            "items": [str(item_id) for item_id in found_ids],
        }
        if payload.dry_run:
            return {"dry_run": True, "replayed": False, **preview}

        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": payload.idempotency_key},
        )
        existing = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.action == "admin_batch.completed",
                    AuditLog.correlation_id == payload.idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {"dry_run": False, "replayed": True, **existing.payload}

        now = datetime.now(timezone.utc)
        changed = 0
        if payload.kind == "comments":
            deleted = payload.action == "delete"
            for item in comment_rows:
                previous = item.is_deleted
                if item.is_deleted != deleted:
                    item.is_deleted = deleted
                    item.deleted_at = now if deleted else None
                    item.deleted_by_admin_id = admin.telegram_id if deleted else None
                    changed += 1
                session.add(
                    AuditLog(
                        actor_telegram_id=admin.telegram_id,
                        action="comments.batch_updated",
                        entity_type="comment",
                        entity_id=str(item.id),
                        payload={
                            "previous": previous,
                            "next": deleted,
                            "note": payload.note,
                        },
                        correlation_id=payload.idempotency_key,
                    )
                )
        elif payload.kind == "ratings":
            for item in rating_rows:
                previous = item.status
                if item.status != payload.action:
                    item.status = payload.action
                    session.add(
                        TranslationRatingStatusHistory(
                            rating_id=item.id,
                            old_status=previous,
                            new_status=payload.action,
                            admin_telegram_id=admin.telegram_id,
                            note=payload.note,
                        )
                    )
                    changed += 1
                session.add(
                    AuditLog(
                        actor_telegram_id=admin.telegram_id,
                        action="ratings.batch_updated",
                        entity_type="rating",
                        entity_id=str(item.id),
                        payload={
                            "previous": previous,
                            "next": payload.action,
                            "note": payload.note,
                        },
                        correlation_id=payload.idempotency_key,
                    )
                )
        else:
            for item in report_rows:
                previous = item.status
                if item.status != payload.action:
                    item.status = payload.action
                    item.assigned_admin_id = admin.telegram_id
                    changed += 1
                session.add(
                    AuditLog(
                        actor_telegram_id=admin.telegram_id,
                        action="reports.batch_updated",
                        entity_type="report",
                        entity_id=str(item.id),
                        payload={
                            "previous": previous,
                            "next": payload.action,
                            "note": payload.note,
                        },
                        correlation_id=payload.idempotency_key,
                    )
                )

        result = {**preview, "changed": changed}
        session.add(
            AuditLog(
                actor_telegram_id=admin.telegram_id,
                action="admin_batch.completed",
                entity_type="admin_batch",
                entity_id=payload.idempotency_key,
                payload=result,
                correlation_id=payload.idempotency_key,
            )
        )
        await session.commit()
        return {"dry_run": False, "replayed": False, **result}
