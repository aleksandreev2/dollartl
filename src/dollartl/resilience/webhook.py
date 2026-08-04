from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from dollartl.config import Settings
from dollartl.db.resilience_models import TelegramUpdateReceipt
from dollartl.db.session import SessionFactory


async def claim_update(update_id: int, settings: Settings) -> bool:
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(seconds=settings.webhook_receipt_stale_seconds)
    async with SessionFactory() as session:
        created = (
            await session.execute(
                insert(TelegramUpdateReceipt)
                .values(
                    id=uuid4(),
                    update_id=update_id,
                    status="processing",
                    attempts=1,
                    started_at=now,
                    last_error=None,
                )
                .on_conflict_do_nothing(
                    constraint="uq_telegram_update_receipts_update_id"
                )
                .returning(TelegramUpdateReceipt.id)
            )
        ).scalar_one_or_none()
        if created is not None:
            await session.commit()
            return True

        receipt = (
            await session.execute(
                select(TelegramUpdateReceipt)
                .where(TelegramUpdateReceipt.update_id == update_id)
                .with_for_update()
            )
        ).scalar_one()
        if receipt.status == "completed":
            await session.commit()
            return False
        if receipt.status == "processing" and receipt.started_at > stale_before:
            await session.commit()
            return False
        receipt.status = "processing"
        receipt.attempts += 1
        receipt.started_at = now
        receipt.completed_at = None
        receipt.last_error = None
        await session.commit()
        return True


async def complete_update(update_id: int) -> None:
    async with SessionFactory() as session:
        receipt = (
            await session.execute(
                select(TelegramUpdateReceipt)
                .where(TelegramUpdateReceipt.update_id == update_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if receipt is None:
            return
        receipt.status = "completed"
        receipt.completed_at = datetime.now(timezone.utc)
        receipt.last_error = None
        await session.commit()


async def fail_update(update_id: int, error: BaseException) -> None:
    async with SessionFactory() as session:
        receipt = (
            await session.execute(
                select(TelegramUpdateReceipt)
                .where(TelegramUpdateReceipt.update_id == update_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if receipt is None:
            return
        receipt.status = "failed"
        receipt.last_error = f"{type(error).__name__}: {error}"[:4000]
        await session.commit()
