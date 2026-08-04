import re

from dollartl.services.catalog import generate_deep_link_token, normalize_title, slugify


def test_slugify_is_stable() -> None:
    assert slugify("My Title: Volume 1") == "my-title-volume-1"


def test_normalize_title_handles_punctuation() -> None:
    assert normalize_title("  My—Title!! ") == "my title"


def test_deep_link_token_is_telegram_safe() -> None:
    token = generate_deep_link_token()
    assert 8 <= len(token) <= 64
    assert re.fullmatch(r"[A-Za-z0-9_-]+", token)
