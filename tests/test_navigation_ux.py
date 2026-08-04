from dollartl.bot.keyboards import (
    NAV_CANCEL,
    NAV_SEARCH,
    home_keyboard,
    persistent_navigation_keyboard,
    search_prompt_keyboard,
)


def _button_texts(markup: object) -> list[str]:
    rows = getattr(markup, "keyboard", None) or getattr(markup, "inline_keyboard", [])
    return [button.text for row in rows for button in row]


def test_persistent_navigation_keeps_search_and_cancel() -> None:
    texts = _button_texts(persistent_navigation_keyboard())
    assert NAV_SEARCH in texts
    assert NAV_CANCEL in texts
    assert len(texts) == 7


def test_home_message_keeps_full_inline_navigation() -> None:
    texts = _button_texts(home_keyboard())
    assert "🆕 Latest Releases" in texts
    assert "📚 Browse Titles" in texts
    assert "🔎 Search" in texts
    assert "📖 My Library" in texts
    assert "💎 Boosty Access" in texts
    assert "💡 Suggest a Title" in texts


def test_search_prompt_has_inline_cancel() -> None:
    texts = _button_texts(search_prompt_keyboard())
    assert "❌ Cancel Search" in texts
