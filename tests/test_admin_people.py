import pytest
from pydantic import ValidationError

from dollartl.admin.people_common import BatchModerationRequest, page_meta


def test_page_meta_handles_empty_result() -> None:
    assert page_meta(total=0, page=1, page_size=30) == {
        "page": 1,
        "page_size": 30,
        "total": 0,
        "pages": 1,
    }


def test_batch_request_accepts_valid_action() -> None:
    payload = BatchModerationRequest(
        kind="ratings",
        ids=["00000000-0000-0000-0000-000000000001"],
        action="fixed",
        dry_run=True,
        idempotency_key="admin-ratings-123456",
    )
    assert payload.action == "fixed"


def test_batch_request_rejects_cross_kind_action() -> None:
    with pytest.raises(ValidationError):
        BatchModerationRequest(
            kind="comments",
            ids=["00000000-0000-0000-0000-000000000001"],
            action="resolved",
            dry_run=True,
            idempotency_key="admin-comments-123456",
        )


def test_batch_request_rejects_duplicate_ids() -> None:
    with pytest.raises(ValidationError):
        BatchModerationRequest(
            kind="reports",
            ids=[
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000001",
            ],
            action="resolved",
            dry_run=True,
            idempotency_key="admin-reports-123456",
        )
