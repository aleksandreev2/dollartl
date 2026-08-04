from datetime import datetime, timezone

import pytest

from dollartl.services.suggestion_helpers import (
    detect_title_language,
    normalize_source_url,
    parse_source_lines,
    quota_limit,
    quota_month,
    requested_scope,
)


def test_source_normalization_removes_tracking_and_fragment() -> None:
    value = normalize_source_url(
        "HTTPS://Example.COM/novel/?utm_source=x&id=7#chapter"
    )
    assert value == "https://example.com/novel?id=7"


def test_invalid_source_is_rejected() -> None:
    with pytest.raises(ValueError):
        parse_source_lines("ftp://example.com/book", 10)


def test_scope_and_quota() -> None:
    assert requested_scope(chapter_count=318, vip=False, standard_cap=200) == (1, 200)
    assert requested_scope(chapter_count=318, vip=True, standard_cap=200) == (1, 318)
    assert quota_limit(vip=False, standard_limit=1, vip_limit=5) == 1
    assert quota_limit(vip=True, standard_limit=1, vip_limit=5) == 5


def test_calendar_month_and_language() -> None:
    moment = datetime(2026, 8, 31, tzinfo=timezone.utc)
    assert quota_month(moment).isoformat() == "2026-08-01"
    assert detect_title_language("나 혼자만 레벨업") == "Korean"
