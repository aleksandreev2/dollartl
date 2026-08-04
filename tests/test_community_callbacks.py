from types import SimpleNamespace
from uuid import uuid4

from dollartl.bot.community_keyboards import (
    comments_keyboard,
    rating_categories_keyboard,
    report_categories_keyboard,
)
from dollartl.bot.keyboards import release_keyboard, title_keyboard


def _assert_callback_lengths(markup: object) -> None:
    for row in markup.inline_keyboard:
        for button in row:
            if button.callback_data is not None:
                assert len(button.callback_data.encode("utf-8")) <= 64


def test_community_callback_data_fits_telegram_limit() -> None:
    target_id = uuid4()
    _assert_callback_lengths(
        comments_keyboard(
            target_type="release",
            target_id=target_id,
            page=12,
            has_next=True,
        )
    )
    _assert_callback_lengths(
        rating_categories_keyboard(
            target_id,
            {"terminology", "formatting"},
            3,
        )
    )
    _assert_callback_lengths(report_categories_keyboard("release", target_id))


def test_title_and_release_keyboards_include_community_actions() -> None:
    title_id = uuid4()
    release_id = uuid4()
    title = SimpleNamespace(
        id=title_id,
        english_title="Example",
        boosty_url="https://boosty.to/example",
    )
    release = SimpleNamespace(
        id=release_id,
        title_id=title_id,
        chapter_label="Chapters 1–20",
    )
    title_markup = title_keyboard(title, [release], followed=False)
    release_markup = release_keyboard(
        release,
        direct_download=True,
        boosty_url="https://boosty.to/example/post",
    )
    title_texts = {button.text for row in title_markup.inline_keyboard for button in row}
    release_texts = {button.text for row in release_markup.inline_keyboard for button in row}
    assert "💝 Donate" in title_texts
    assert "Thank you." in title_texts
    assert "⭐ Rate Translation" in release_texts
    _assert_callback_lengths(title_markup)
    _assert_callback_lengths(release_markup)
