from datetime import datetime, timezone

import pytest

from dollartl.bot.admin import parse_duration, resolve_reason
from dollartl.bot.texts import ADULT_NOTICE, render_permanent_ban, render_temporary_ban


def test_parse_temporary_duration() -> None:
    now = datetime(2026, 8, 4, 16, 0, tzinfo=timezone.utc)
    ban_type, expires_at = parse_duration("7d", now=now)
    assert ban_type == "temporary"
    assert expires_at == datetime(2026, 8, 11, 16, 0, tzinfo=timezone.utc)


def test_parse_permanent_duration() -> None:
    assert parse_duration("permanent") == ("permanent", None)


def test_invalid_duration_is_rejected() -> None:
    with pytest.raises(ValueError):
        parse_duration("tomorrow")


def test_reason_template_and_custom_reason() -> None:
    template_reason, template_key = resolve_reason("spam")
    assert template_key == "spam"
    assert "spam" in template_reason.lower()
    custom_reason, custom_key = resolve_reason("A custom public reason.")
    assert custom_key is None
    assert custom_reason == "A custom public reason."


def test_temporary_ban_message_uses_configured_timezone() -> None:
    text = render_temporary_ban(
        expires_at=datetime(2026, 9, 4, 15, 30, tzinfo=timezone.utc),
        reason="Repeated violations.",
        timezone_name="Asia/Yerevan",
    )
    assert "04-09-2026 19:30 UTC+04:00" in text
    assert "Repeated violations." in text


def test_permanent_ban_message() -> None:
    text = render_permanent_ban(reason="Repeated serious violations.")
    assert "end of time" in text
    assert "Unfortunately" in text


def test_adult_notice_covers_higher_local_age_and_legality() -> None:
    assert "higher minimum legal age" in ADULT_NOTICE
    assert "lawful where you live" in ADULT_NOTICE
