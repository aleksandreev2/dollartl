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


def test_title_keyboard_places_thanks_before_donate_and_follow_novel() -> None:
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

    markup = title_keyboard(
        title,
        [release],
        followed=False,
        thanked=False,
        direct_download=False,
    )
    rows = markup.inline_keyboard
    texts = [[button.text for button in row] for row in rows]

    assert ["Thank you."] in texts
    assert ["💝 Donate", "🔔 Follow Novel"] in texts
    thank_button = next(button for row in rows for button in row if button.text == "Thank you.")
    assert thank_button.callback_data == f"community:thanks:{title_id}"
    assert not any(button.text == "⬇️ Download" for row in rows for button in row)
    _assert_callback_lengths(markup)


def test_thanked_title_keyboard_shows_download_for_each_release() -> None:
    title_id = uuid4()
    releases = [
        SimpleNamespace(
            id=uuid4(),
            title_id=title_id,
            chapter_label="Chapters 1–20",
        ),
        SimpleNamespace(
            id=uuid4(),
            title_id=title_id,
            chapter_label="Chapters 21–40",
        ),
    ]
    title = SimpleNamespace(
        id=title_id,
        english_title="Example",
        boosty_url="https://boosty.to/example",
    )

    markup = title_keyboard(
        title,
        releases,
        followed=True,
        thanked=True,
        direct_download=True,
    )
    buttons = [button for row in markup.inline_keyboard for button in row]

    assert sum(button.text == "⬇️ Download" for button in buttons) == 2
    assert "✅ Thank you." in {button.text for button in buttons}
    assert "🔕 Unfollow Novel" in {button.text for button in buttons}
    for release in releases:
        assert any(
            button.callback_data == f"catalog:download:{release.id}"
            for button in buttons
        )
    _assert_callback_lengths(markup)


def test_release_keyboard_includes_community_actions() -> None:
    title_id = uuid4()
    release_id = uuid4()
    release = SimpleNamespace(
        id=release_id,
        title_id=title_id,
        chapter_label="Chapters 1–20",
    )
    release_markup = release_keyboard(
        release,
        direct_download=True,
        boosty_url="https://boosty.to/example/post",
    )
    release_texts = {
        button.text for row in release_markup.inline_keyboard for button in row
    }
    assert "⭐ Rate Translation" in release_texts
    _assert_callback_lengths(release_markup)
