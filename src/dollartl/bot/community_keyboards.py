from __future__ import annotations

from uuid import UUID

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

RATING_CATEGORY_LABELS = {
    "accuracy": "Translation Accuracy",
    "unnatural": "Unnatural English",
    "grammar": "Grammar or Punctuation",
    "terminology": "Inconsistent Terminology",
    "names": "Names or Pronouns",
    "missing": "Missing or Duplicated Text",
    "formatting": "Formatting or Layout",
    "pdf": "PDF Problem",
    "epub": "EPUB Problem",
    "other": "Other",
    "no_issues": "No Issues Found",
}

REPORT_CATEGORY_LABELS = {
    "broken_pdf": "Broken PDF",
    "broken_epub": "Broken EPUB",
    "missing_chapters": "Missing Chapters",
    "wrong_order": "Wrong Chapter Order",
    "metadata": "Incorrect Title Information",
    "boosty_access": "Boosty Access Problem",
    "other": "Other",
}


def _short_target(target_type: str) -> str:
    return "t" if target_type == "title" else "r"


def comments_keyboard(
    *,
    target_type: str,
    target_id: UUID,
    page: int,
    has_next: bool,
) -> InlineKeyboardMarkup:
    short = _short_target(target_type)
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="✍️ Write a Comment",
                callback_data=f"cm:add:{short}:{target_id}",
            ),
            InlineKeyboardButton(
                text="📝 My Comments",
                callback_data="cm:mine",
            ),
        ]
    ]
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="◀️ Previous",
                callback_data=f"cm:ls:{short}:{target_id}:{page - 1}",
            )
        )
    if has_next:
        nav.append(
            InlineKeyboardButton(
                text="Next ▶️",
                callback_data=f"cm:ls:{short}:{target_id}:{page + 1}",
            )
        )
    if nav:
        rows.append(nav)
    back = (
        f"catalog:title:{target_id}"
        if target_type == "title"
        else f"catalog:release:{target_id}"
    )
    rows.append([InlineKeyboardButton(text="◀️ Back", callback_data=back)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def rating_stars_keyboard(release_id: UUID) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{score} ⭐",
                    callback_data=f"cm:rs:{release_id}:{score}",
                )
                for score in range(1, 6)
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Back to Release",
                    callback_data=f"catalog:release:{release_id}",
                )
            ],
        ]
    )


def rating_categories_keyboard(
    release_id: UUID, selected: set[str], score: int
) -> InlineKeyboardMarkup:
    codes = [
        "accuracy",
        "unnatural",
        "grammar",
        "terminology",
        "names",
        "missing",
        "formatting",
        "pdf",
        "epub",
        "other",
    ]
    if score == 5:
        codes.insert(0, "no_issues")
    rows: list[list[InlineKeyboardButton]] = []
    for code in codes:
        mark = "✅ " if code in selected else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark}{RATING_CATEGORY_LABELS[code]}",
                    callback_data=f"cm:rc:{release_id}:{code}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="Continue",
                callback_data=f"cm:rd:{release_id}",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data=f"catalog:release:{release_id}",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_categories_keyboard(
    target_type: str, target_id: UUID
) -> InlineKeyboardMarkup:
    short = _short_target(target_type)
    rows = [
        [
            InlineKeyboardButton(
                text=label,
                callback_data=f"cm:pc:{short}:{target_id}:{code}",
            )
        ]
        for code, label in REPORT_CATEGORY_LABELS.items()
    ]
    back = (
        f"catalog:title:{target_id}"
        if target_type == "title"
        else f"catalog:release:{target_id}"
    )
    rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data=back)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def nickname_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🕶 Use Anonymous Name",
                    callback_data="community:nickname:anonymous",
                )
            ],
            [InlineKeyboardButton(text="◀️ Back", callback_data="menu:settings")],
        ]
    )


def my_comments_keyboard(comment_ids: list[UUID]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"🗑 Delete {str(comment_id)[:8]}",
                callback_data=f"cm:del:{comment_id}",
            )
        ]
        for comment_id in comment_ids
    ]
    rows.append([InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
