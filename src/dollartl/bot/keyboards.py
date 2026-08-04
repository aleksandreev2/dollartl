from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def adult_consent_keyboard(version: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔞 I Confirm and Continue",
                    callback_data=f"consent:adult:{version}",
                )
            ]
        ]
    )


def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🆕 Latest Releases", callback_data="soon:latest")],
            [InlineKeyboardButton(text="📚 Browse Titles", callback_data="soon:catalogue")],
            [
                InlineKeyboardButton(text="💎 Boosty Access", callback_data="soon:boosty"),
                InlineKeyboardButton(text="📖 My Library", callback_data="soon:library"),
            ],
            [
                InlineKeyboardButton(text="💡 Suggest a Title", callback_data="soon:suggest"),
                InlineKeyboardButton(text="📋 My Suggestions", callback_data="soon:my_suggestions"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Settings", callback_data="menu:settings"),
                InlineKeyboardButton(text="❓ Help", callback_data="menu:help"),
            ],
        ]
    )


def settings_keyboard(new_title_announcements: bool) -> InlineKeyboardMarkup:
    status = "ON" if new_title_announcements else "OFF"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🔔 New Title Announcements: {status}",
                    callback_data="settings:toggle:new_titles",
                )
            ],
            [InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:home")],
        ]
    )


def back_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:home")]
        ]
    )
