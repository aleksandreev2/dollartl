from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from dollartl.admin.catalog_ops_common import ensure_not_conflicted, normalized_aliases


def test_normalized_aliases_deduplicates_case_and_spacing() -> None:
    values = normalized_aliases(" Solo Leveling ", "solo   leveling", "나 혼자만 레벨업")
    assert len(values) == 2
    assert values[0][1] in {"Solo Leveling", "나 혼자만 레벨업"}


def test_optimistic_lock_accepts_same_timestamp() -> None:
    value = datetime(2026, 8, 5, 6, 0, tzinfo=timezone.utc)
    ensure_not_conflicted(value, value)


def test_optimistic_lock_rejects_stale_timestamp() -> None:
    current = datetime(2026, 8, 5, 6, 0, tzinfo=timezone.utc)
    stale = datetime(2026, 8, 5, 5, 59, tzinfo=timezone.utc)
    with pytest.raises(HTTPException) as exc:
        ensure_not_conflicted(current, stale)
    assert exc.value.status_code == 409
