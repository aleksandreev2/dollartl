from uuid import UUID

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from dollartl.db.models import Release, Title

DONATE_URL = "https://boosty.to/domnekromanta/single-payment/donation/818248/target?share=target_link"

NAV_HOME = "🏠 Home"
NAV_LATEST = "🆕 Latest"
NAV_BROWSE = "📚 Browse"
NAV_SEARCH = "🔎 Search"
NAV_LIBRARY = "📖 Library"
NAV_MENU = "☰ Menu"
NAV_CANCEL = "❌ /cancel"


def persistent_navigation_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=NAV_HOME), KeyboardButton(text=NAV_LATEST)],
            [KeyboardButton(text=NAV_BROWSE), KeyboardButton(text=NAV_SEARCH)],
            [KeyboardButton(text=NAV_LIBRARY), KeyboardButton(text=NAV_MENU)],
            [KeyboardButton(text=NAV_CANCEL)],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
        input_field_placeholder="Choose an action or type /cancel",
    )


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
    """Full inline home menu shown under the home card.

    The persistent reply keyboard remains available independently after it has
    been installed once, so the two navigation surfaces complement rather than
    replace one another.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🆕 Latest Releases", callback_data="catalog:latest:0"
                ),
                InlineKeyboardButton(
                    text="📚 Browse Titles", callback_data="catalog:list:0"
                ),
            ],
            [
                InlineKeyboardButton(text="🔎 Search", callback_data="catalog:search"),
                InlineKeyboardButton(
                    text="📖 My Library", callback_data="catalog:library"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💎 Boosty Access", callback_data="boosty:menu"
                ),
                InlineKeyboardButton(
                    text="💡 Suggest a Title", callback_data="menu:suggest"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📋 My Suggestions", callback_data="sug:mine"
                ),
                InlineKeyboardButton(
                    text="⚙️ Settings", callback_data="menu:settings"
                ),
            ],
            [InlineKeyboardButton(text="❓ Help", callback_data="menu:help")],
        ]
    )


def search_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Cancel Search", callback_data="catalog:search:cancel"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📚 Browse Instead", callback_data="catalog:list:0"
                ),
                InlineKeyboardButton(text="🏠 Main Menu", callback_data="menu:home"),
            ],
        ]
    )


def settings_keyboard(new_title_announcements: bool) -> InlineKeyboardMarkup:
    status = "ON" if new_title_announcements else "OFF"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 Display Name",
                    callback_data="community:nickname",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🔔 New Title Announcements: {status}",
                    callback_data="settings:toggle:new_titles",
                )
            ],
            [InlineKeyboardButton(text="💎 Boosty Account", callback_data="boosty:menu")],
            [InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:home")],
        ]
    )


def catalogue_keyboard(
    titles: list[Title], *, page: int, has_next: bool
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=title.english_title[:55],
                callback_data=f"catalog:title:{title.id}",
            )
        ]
        for title in titles
    ]
    navigation: list[InlineKeyboardButton] = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="◀️ Previous", callback_data=f"catalog:list:{page - 1}"
            )
        )
    if has_next:
        navigation.append(
            InlineKeyboardButton(
                text="Next ▶️", callback_data=f"catalog:list:{page + 1}"
            )
        )
    if navigation:
        rows.append(navigation)
    rows.extend(
        [
            [InlineKeyboardButton(text="🔎 Search", callback_data="catalog:search")],
            [InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:home")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def latest_keyboard(
    releases: list[Release],
    titles: dict[UUID, Title],
    *,
    page: int,
    has_next: bool,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for release in releases:
        title = titles.get(release.title_id)
        label = f"{title.english_title if title else 'Title'} · {release.chapter_label}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label[:60],
                    callback_data=f"catalog:release:{release.id}",
                )
            ]
        )
    navigation: list[InlineKeyboardButton] = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="◀️ Previous", callback_data=f"catalog:latest:{page - 1}"
            )
        )
    if has_next:
        navigation.append(
            InlineKeyboardButton(
                text="Next ▶️", callback_data=f"catalog:latest:{page + 1}"
            )
        )
    if navigation:
        rows.append(navigation)
    rows.extend(
        [
            [InlineKeyboardButton(text="🔎 Search Titles", callback_data="catalog:search")],
            [InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:home")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def search_results_keyboard(titles: list[Title]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=title.english_title[:55],
                callback_data=f"catalog:title:{title.id}",
            )
        ]
        for title in titles
    ]
    rows.extend(
        [
            [InlineKeyboardButton(text="🔎 Search Again", callback_data="catalog:search")],
            [
                InlineKeyboardButton(
                    text="📚 Browse Titles", callback_data="catalog:list:0"
                ),
                InlineKeyboardButton(text="🏠 Main Menu", callback_data="menu:home"),
            ],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def title_keyboard(
    title: Title,
    releases: list[Release],
    *,
    followed: bool,
    thanked: bool = False,
    direct_download: bool = False,
    donate_url: str = DONATE_URL,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for release in releases:
        release_row = [
            InlineKeyboardButton(
                text=f"📦 {release.chapter_label}",
                callback_data=f"catalog:release:{release.id}",
            )
        ]
        if direct_download:
            release_row.append(
                InlineKeyboardButton(
                    text="⬇️ Download",
                    callback_data=f"catalog:download:{release.id}",
                )
            )
        rows.append(release_row)
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="💬 Comments", callback_data=f"cm:ls:t:{title.id}:0"
                ),
                InlineKeyboardButton(
                    text="⚠️ Report",
                    callback_data=f"community:report:title:{title.id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⭐ Translation Rating",
                    callback_data=f"community:title_rating:{title.id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Thank you." if thanked else "Thank you.",
                    callback_data=f"community:thanks:{title.id}",
                )
            ],
            [
                InlineKeyboardButton(text="💝 Donate", url=donate_url),
                InlineKeyboardButton(
                    text="🔕 Unfollow Novel" if followed else "🔔 Follow Novel",
                    callback_data=f"catalog:follow:{title.id}",
                ),
            ],
        ]
    )
    if title.boosty_url:
        rows.append(
            [InlineKeyboardButton(text="🌐 Open on Boosty", url=title.boosty_url)]
        )
    rows.extend(
        [
            [InlineKeyboardButton(text="🔎 Search Titles", callback_data="catalog:search")],
            [
                InlineKeyboardButton(
                    text="◀️ Browse Titles", callback_data="catalog:list:0"
                )
            ],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def release_keyboard(
    release: Release,
    *,
    direct_download: bool,
    boosty_url: str | None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if direct_download:
        rows.append(
            [
                InlineKeyboardButton(
                    text="⬇️ Download PDF + EPUB",
                    callback_data=f"catalog:download:{release.id}",
                )
            ]
        )
    elif boosty_url:
        rows.append(
            [InlineKeyboardButton(text="🌐 Open Boosty Publication", url=boosty_url)]
        )
    else:
        rows.append(
            [InlineKeyboardButton(text="💎 Boosty Access", callback_data="boosty:menu")]
        )
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="💬 Comments", callback_data=f"cm:ls:r:{release.id}:0"
                ),
                InlineKeyboardButton(
                    text="⭐ Rate Translation",
                    callback_data=f"community:rate:{release.id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚠️ Report a Problem",
                    callback_data=f"community:report:release:{release.id}",
                )
            ],
            [InlineKeyboardButton(text="🔎 Search Titles", callback_data="catalog:search")],
            [
                InlineKeyboardButton(
                    text="◀️ Back to Title",
                    callback_data=f"catalog:title:{release.title_id}",
                )
            ],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def library_keyboard(titles: list[Title]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=title.english_title[:55],
                callback_data=f"catalog:title:{title.id}",
            )
        ]
        for title in titles
    ]
    rows.extend(
        [
            [InlineKeyboardButton(text="🔎 Search Titles", callback_data="catalog:search")],
            [
                InlineKeyboardButton(
                    text="📚 Browse Titles", callback_data="catalog:list:0"
                )
            ],
            [InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:home")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:home")]
        ]
    )
