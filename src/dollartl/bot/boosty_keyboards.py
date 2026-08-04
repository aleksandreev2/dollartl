from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from dollartl.config import Settings


def boosty_status_keyboard(status: str, settings: Settings) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if status in {"unverified", "expired", "verification_error"}:
        rows.append(
            [InlineKeyboardButton(text="🔗 Verify Membership", callback_data="boosty:verify")]
        )
        rows.append(
            [InlineKeyboardButton(text="🌐 Open Boosty", url=settings.boosty_membership_url)]
        )
    elif status == "grace_period":
        rows.append(
            [InlineKeyboardButton(text="🌐 Renew on Boosty", url=settings.boosty_membership_url)]
        )
        rows.append(
            [InlineKeyboardButton(text="🔄 Check Membership", callback_data="boosty:check")]
        )
    else:
        rows.append(
            [InlineKeyboardButton(text="🔄 Check Membership", callback_data="boosty:check")]
        )
        rows.append(
            [InlineKeyboardButton(text="📚 Browse Titles", callback_data="catalog:list:0")]
        )
    rows.append([InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def boosty_code_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Open Boosty Messages", url=settings.boosty_messages_url)],
            [InlineKeyboardButton(text="🔄 Check Status", callback_data="boosty:check")],
            [InlineKeyboardButton(text="◀️ Boosty Access", callback_data="boosty:status")],
        ]
    )
