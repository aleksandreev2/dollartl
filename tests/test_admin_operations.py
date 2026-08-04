from uuid import UUID

from dollartl.admin.operations_router import (
    attention_item,
    normalize_query,
    numeric_query,
    search_result,
    trim,
    uuid_query,
)


def test_query_normalization_and_identifiers() -> None:
    assert normalize_query("  Anonymous   12  ") == "Anonymous 12"
    assert numeric_query("Anonymous 12") == 12
    assert numeric_query("  2096975784 ") == 2096975784
    assert numeric_query("@someone") is None

    value = "0f3f6e08-55ce-4e66-bb29-d16518aebacd"
    assert uuid_query(value) == UUID(value)
    assert uuid_query("not-a-uuid") is None


def test_operations_serializers_trim_long_text() -> None:
    long_text = "word " * 100
    attention = attention_item(
        kind="report",
        entity_id="1",
        severity="high",
        title="Report",
        description=long_text,
        section="community",
        created_at=None,
    )
    result = search_result(
        kind="title",
        entity_id="2",
        title=long_text,
        subtitle=long_text,
        section="catalog",
        created_at=None,
    )

    assert len(attention["description"]) <= 180
    assert attention["description"].endswith("…")
    assert len(result["title"]) <= 140
    assert len(result["subtitle"]) <= 220
    assert trim("  a   b  ") == "a b"
