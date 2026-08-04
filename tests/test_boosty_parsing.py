from datetime import datetime, timedelta, timezone

from dollartl.integrations.boosty import (
    _extract_identity,
    _extract_membership,
    _payload_contains_code,
)
from dollartl.services.boosty import BoostyStatus


def test_verification_code_is_found_recursively() -> None:
    payload = {"messages": [{"content": [{"type": "text", "text": "My code is DL-AB12-CD34"}]}]}
    assert _payload_contains_code(payload, "DL-AB12-CD34")


def test_identity_is_read_from_nested_user() -> None:
    identity = _extract_identity({"user": {"id": 42, "name": "reader"}})
    assert identity is not None
    assert identity.user_id == "42"
    assert identity.username == "reader"


def test_membership_reads_level_and_false_string() -> None:
    membership = _extract_membership(
        {
            "user": {"id": 42, "name": "reader"},
            "subscriptionLevel": {"id": 4041120, "name": "Comrade Xi"},
            "active": "false",
        }
    )
    assert membership is not None
    assert membership.tier_id == "4041120"
    assert membership.active is False


def test_grace_status_requires_future_expiration() -> None:
    future = BoostyStatus(
        status="grace_period", grace_ends_at=datetime.now(timezone.utc) + timedelta(days=1)
    )
    past = BoostyStatus(
        status="grace_period", grace_ends_at=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    assert future.has_download_access is True
    assert past.has_download_access is False
