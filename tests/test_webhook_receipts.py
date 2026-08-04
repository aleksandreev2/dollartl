from __future__ import annotations

from uuid import uuid4

from sqlalchemy import delete

from dollartl.config import Settings
from dollartl.db.resilience_models import TelegramUpdateReceipt
from dollartl.db.session import SessionFactory
from dollartl.resilience.webhook import claim_update, complete_update, fail_update


async def test_webhook_receipt_lifecycle() -> None:
    update_id = uuid4().int % 9_000_000_000_000_000_000
    settings = Settings(webhook_receipt_stale_seconds=300)
    try:
        assert await claim_update(update_id, settings) is True
        assert await claim_update(update_id, settings) is False

        await fail_update(update_id, RuntimeError("temporary failure"))
        assert await claim_update(update_id, settings) is True

        await complete_update(update_id)
        assert await claim_update(update_id, settings) is False
    finally:
        async with SessionFactory() as session:
            await session.execute(
                delete(TelegramUpdateReceipt).where(
                    TelegramUpdateReceipt.update_id == update_id
                )
            )
            await session.commit()
