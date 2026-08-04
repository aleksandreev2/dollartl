from dollartl.config import Settings


def test_webhook_url_is_normalized() -> None:
    settings = Settings(telegram_webhook_base_url="https://example.com/")
    assert settings.webhook_url == "https://example.com/telegram/webhook"


def test_admin_id_default() -> None:
    assert Settings().admin_telegram_id == 2096975784
