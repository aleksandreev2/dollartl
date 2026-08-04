from __future__ import annotations

from uuid import UUID

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from dollartl.db.suggestion_models import TitleSuggestion
from dollartl.services.suggestions import PUBLIC_STATUS


def rules_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ I Agree to the Rules", callback_data="sug:rules:accept")],
            [InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:home")],
        ]
    )


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💡 Start Suggestion", callback_data="sug:start")],
            [InlineKeyboardButton(text="📋 My Suggestions", callback_data="sug:mine")],
            [InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:home")],
        ]
    )


def publication_status_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📖 Ongoing", callback_data="sug:pub:ongoing"),
                InlineKeyboardButton(text="✅ Completed", callback_data="sug:pub:completed"),
            ],
            [
                InlineKeyboardButton(text="⏸ Hiatus", callback_data="sug:pub:hiatus"),
                InlineKeyboardButton(text="❓ Unknown", callback_data="sug:pub:unknown"),
            ],
            [InlineKeyboardButton(text="❌ Cancel Draft", callback_data="sug:cancel")],
        ]
    )


def skip_file_keyboard(kind: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Skip {kind.title()}", callback_data=f"sug:skip:{kind}")],
            [InlineKeyboardButton(text="❌ Cancel Draft", callback_data="sug:cancel")],
        ]
    )


def review_keyboard(suggestion_id: UUID) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Submit Suggestion", callback_data=f"sug:submit:{suggestion_id}")],
            [InlineKeyboardButton(text="❌ Cancel Draft", callback_data="sug:cancel")],
        ]
    )


def suggestions_list_keyboard(items: list[TitleSuggestion]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{PUBLIC_STATUS.get(item.status, item.status)} · {(item.original_title or 'Untitled')[:35]}",
                callback_data=f"sug:view:{item.id}",
            )
        ]
        for item in items
    ]
    rows.extend(
        [
            [InlineKeyboardButton(text="💡 New Suggestion", callback_data="menu:suggest")],
            [InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:home")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def suggestion_view_keyboard(linked_title_id: UUID | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if linked_title_id is not None:
        rows.append(
            [
                InlineKeyboardButton(
                    text="📚 Open Translated Title",
                    callback_data=f"catalog:title:{linked_title_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="◀️ My Suggestions", callback_data="sug:mine")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
