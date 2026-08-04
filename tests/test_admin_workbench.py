from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from dollartl.admin.workbench_router import page_meta, safe_setting_key, setting_conflicts


def test_page_meta_never_returns_zero_pages() -> None:
    assert page_meta(total=0, page=1, page_size=30) == {
        "page": 1,
        "page_size": 30,
        "total": 0,
        "pages": 1,
    }
    assert page_meta(total=61, page=2, page_size=30)["pages"] == 3


def test_setting_key_rejects_secrets_and_invalid_names() -> None:
    assert safe_setting_key("channel.posts.enabled") is True
    assert safe_setting_key("backup_retention_count") is True
    assert safe_setting_key("telegram_bot_token") is False
    assert safe_setting_key("S3_SECRET_ACCESS_KEY") is False
    assert safe_setting_key("backup_encryption_key") is False
    assert safe_setting_key("boosty_credentials") is False
    assert safe_setting_key("not allowed") is False


def test_setting_conflict_uses_optimistic_timestamp() -> None:
    current = datetime(2026, 8, 5, 1, 0, tzinfo=timezone.utc)
    item = SimpleNamespace(updated_at=current)
    assert setting_conflicts(item, current) is False
    assert setting_conflicts(item, current - timedelta(seconds=1)) is True
    assert setting_conflicts(item, None) is False
