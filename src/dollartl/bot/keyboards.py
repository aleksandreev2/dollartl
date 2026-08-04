from uuid import UUID

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from dollartl.db.models import Release, Title

DONATE_URL = "https://boosty.to/domnekromanta/single-payment/donation/818248/target?share=target_link"


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
            [InlineKeyboardButton(text="🆕 Latest Releases", callback_data="catalog:latest:0")],
            [InlineKeyboardButton(text="📚 Browse Titles", callback_data="catalog:list:0")],
            [
                InlineKeyboardButton(text="💎 Boosty Access", callback_data="boosty:menu"),
                InlineKeyboardButton(text="📖 My Library", callback_data="catalog:library"),
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
                text=title.english_title[:55], callback_data=f"catalog:title:{title.id}"
            )
        ]
        for title in titles
    ]
    navigation: list[InlineKeyboardButton] = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(text="◀️ Previous", callback_data=f"catalog:list:{page - 1}")
        )
    if has_next:
        navigation.append(
            InlineKeyboardButton(text="Next ▶️", callback_data=f"catalog:list:{page + 1}")
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
    releases: list[Release], titles: dict[UUID, Title], *, page: int, has_next: bool
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for release in releases:
        title = titles.get(release.title_id)
        label = f"{title.english_title if title else 'Title'} · {release.chapter_label}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label[:60], callback_data=f"catalog:release:{release.id}"
                )
            ]
        )
    navigation: list[InlineKeyboardButton] = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(text="◀️ Previous", callback_data=f"catalog:latest:{page - 1}")
        )
    if has_next:
        navigation.append(
            InlineKeyboardButton(text="Next ▶️", callback_data=f"catalog:latest:{page + 1}")
        )
    if navigation:
        rows.append(navigation)
    rows.append([InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def search_results_keyboard(titles: list[Title]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=title.english_title[:55], callback_data=f"catalog:title:{title.id}"
            )
        ]
        for title in titles
    ]
    rows.extend(
        [
            [InlineKeyboardButton(text="🔎 Search Again", callback_data="catalog:search")],
            [InlineKeyboardButton(text="◀️ Browse Titles", callback_data="catalog:list:0")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def title_keyboard(
    title: Title,
    releases: list[Release],
    *,
    followed: bool,
    donate_url: str = DONATE_URL,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for release in releases:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📦 {release.chapter_label}",
                    callback_data=f"catalog:release:{release.id}",
                )
            ]
        )
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="💬 Comments",
                    callback_data=f"cm:ls:t:{title.id}:0",
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
                    text="🔕 Unfollow Title" if followed else "🔔 Follow Title",
                    callback_data=f"catalog:follow:{title.id}",
                )
            ],
            [
                InlineKeyboardButton(text="💝 Donate", url=donate_url),
                InlineKeyboardButton(text="Thank you.", callback_data="community:thanks"),
            ],
        ]
    )
    if title.boosty_url:
        rows.append([InlineKeyboardButton(text="🌐 Open on Boosty", url=title.boosty_url)])
    rows.append([InlineKeyboardButton(text="◀️ Browse Titles", callback_data="catalog:list:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def release_keyboard(
    release: Release, *, direct_download: bool, boosty_url: str | None
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
        rows.append([InlineKeyboardButton(text="🌐 Open Boosty Publication", url=boosty_url)])
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text="💎 Boosty Access", callback_data="boosty:menu"
                )
            ]
        )
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="💬 Comments",
                    callback_data=f"cm:ls:r:{release.id}:0",
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
            [
                InlineKeyboardButton(
                    text="◀️ Back to Title", callback_data=f"catalog:title:{release.title_id}"
                )
            ],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def library_keyboard(titles: list[Title]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=title.english_title[:55], callback_data=f"catalog:title:{title.id}"
            )
        ]
        for title in titles
    ]
    rows.extend(
        [
            [InlineKeyboardButton(text="📚 Browse Titles", callback_data="catalog:list:0")],
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
