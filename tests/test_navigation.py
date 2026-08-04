from dollartl.bot.keyboards import (
    NAV_BROWSE,
    NAV_CANCEL,
    NAV_HOME,
    NAV_LATEST,
    NAV_LIBRARY,
    NAV_MENU,
    home_keyboard,
    persistent_navigation_keyboard,
)


def test_persistent_navigation_is_compact_and_complete() -> None:
    keyboard = persistent_navigation_keyboard()
    labels = [button.text for row in keyboard.keyboard for button in row]

    assert keyboard.is_persistent is True
    assert keyboard.resize_keyboard is True
    assert len(keyboard.keyboard) == 3
    assert labels == [
        NAV_HOME,
        NAV_LATEST,
        NAV_BROWSE,
        NAV_LIBRARY,
        NAV_MENU,
        NAV_CANCEL,
    ]


def test_secondary_menu_does_not_duplicate_primary_navigation() -> None:
    keyboard = home_keyboard()
    labels = [button.text for row in keyboard.inline_keyboard for button in row]

    assert NAV_HOME not in labels
    assert NAV_LATEST not in labels
    assert NAV_BROWSE not in labels
    assert NAV_LIBRARY not in labels
    assert any("Boosty" in label for label in labels)
    assert any("Suggest" in label for label in labels)
    assert any("Settings" in label for label in labels)
