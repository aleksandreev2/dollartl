from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, BinaryIO

import pytest

from dollartl.api import bootstrap
from dollartl.config import Settings
from dollartl.storage import StoredObject


class FakeStorage:
    def __init__(self) -> None:
        self.bucket = "test-bucket"
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def ensure_bucket_access(self) -> None:
        return None

    def upload_fileobj(
        self,
        fileobj: BinaryIO,
        key: str,
        content_type: str,
    ) -> StoredObject:
        del content_type
        payload = fileobj.read()
        self.objects[key] = payload
        return StoredObject(key=key, size=len(payload), etag="test")

    def download_file(self, key: str, destination: Path) -> Path:
        destination.write_bytes(self.objects[key])
        return destination

    def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.objects.pop(key, None)


class FakeBot:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url
        self.set_webhook_kwargs: dict[str, Any] = {}
        self.commands: list[Any] = []
        self.command_scope: Any = None

    async def get_me(self) -> SimpleNamespace:
        return SimpleNamespace(username="dollartl_test_bot", id=42)

    async def set_my_commands(self, commands: list[Any], scope: Any) -> bool:
        self.commands = commands
        self.command_scope = scope
        return True

    async def set_webhook(self, **kwargs: Any) -> bool:
        self.set_webhook_kwargs = kwargs
        return True

    async def get_webhook_info(self) -> SimpleNamespace:
        return SimpleNamespace(
            url=self.webhook_url,
            pending_update_count=0,
            last_error_message=None,
        )


class FakeDispatcher:
    def resolve_used_update_types(self) -> list[str]:
        return ["message", "callback_query"]


@pytest.mark.asyncio
async def test_verify_storage_round_trip_and_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = FakeStorage()
    monkeypatch.setattr(bootstrap, "S3Storage", lambda settings: storage)

    result = await bootstrap.verify_storage(Settings())

    assert result.bucket == "test-bucket"
    assert result.size > 0
    assert storage.objects == {}
    assert len(storage.deleted) == 1


@pytest.mark.asyncio
async def test_configure_telegram_webhook() -> None:
    settings = Settings(
        telegram_webhook_base_url="https://example.com",
        telegram_webhook_secret="safe_secret-123",
    )
    bot = FakeBot(settings.webhook_url)

    result = await bootstrap.configure_telegram_webhook(
        bot,  # type: ignore[arg-type]
        FakeDispatcher(),  # type: ignore[arg-type]
        settings,
    )

    assert result.username == "dollartl_test_bot"
    assert result.webhook_url == "https://example.com/telegram/webhook"
    assert [command.command for command in bot.commands] == [
        "start",
        "latest",
        "browse",
        "search",
        "library",
        "menu",
        "settings",
        "help",
        "cancel",
        "admin",
    ]
    assert bot.set_webhook_kwargs["secret_token"] == "safe_secret-123"
    assert bot.set_webhook_kwargs["drop_pending_updates"] is False
    assert bot.set_webhook_kwargs["allowed_updates"] == ["message", "callback_query"]


@pytest.mark.asyncio
async def test_configure_telegram_webhook_requires_secret() -> None:
    settings = Settings(telegram_webhook_base_url="https://example.com")

    with pytest.raises(RuntimeError, match="TELEGRAM_WEBHOOK_SECRET"):
        await bootstrap.configure_telegram_webhook(
            FakeBot(settings.webhook_url),  # type: ignore[arg-type]
            FakeDispatcher(),  # type: ignore[arg-type]
            settings,
        )
