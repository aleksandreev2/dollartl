from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from dollartl.db.models import Release, Title

ADULT_NOTICE = """🔞 <b>ADULT CONTENT NOTICE</b>

This bot contains content intended only for adults.

By selecting “I Confirm and Continue”, you confirm that:

• you are at least 18 years old;
• you meet any higher minimum legal age required to access adult content in your country or region;
• accessing this content is lawful where you live;
• you accept responsibility for complying with all applicable local laws.

If any of these statements is not true, do not continue."""

REGISTRATION_COMPLETE = """✅ <b>REGISTRATION COMPLETE</b>

Welcome to Dollar TL.

Your default public name is:

<b>{anonymous_name}</b>

This permanent anonymous identity will be displayed next to your comments until you set a custom nickname in Settings."""

HELP = """❓ <b>HELP</b>

Use the buttons below to browse titles and releases.

An active eligible Boosty membership unlocks protected PDF and EPUB downloads for the entire catalogue. If membership ends, direct access remains available during a 7-day grace period.

System notifications, account restrictions and important rule updates cannot be disabled."""

COMING_SOON = "This section is not available yet."
SEARCH_PROMPT = """🔎 <b>SEARCH TITLES</b>

Send the original, English or alternative title in one message."""
NO_SEARCH_RESULTS = "No published titles matched your search."
NO_TITLES = "No titles have been published yet."
NO_RELEASES = "No release packages have been published for this title yet."


def render_title(title: Title) -> str:
    status = title.publication_status.capitalize()
    latest = str(title.latest_chapter) if title.latest_chapter else "Not released yet"
    description = escape(title.description.strip()) if title.description.strip() else "No description yet."
    return (
        f"📘 <b>{escape(title.english_title)}</b>\n\n"
        f"<b>Original title:</b>\n{escape(title.original_title)}\n\n"
        f"<b>Language:</b> {escape(title.original_language)}\n"
        f"<b>Status:</b> {escape(status)}\n"
        f"<b>Latest chapter:</b> {latest}\n\n"
        f"<b>Description:</b>\n{description}"
    )


def render_release(title: Title, release: Release) -> str:
    published = (
        release.published_at.strftime("%d-%m-%Y") if release.published_at else "Not published"
    )
    return (
        f"📦 <b>{escape(release.chapter_label)}</b>\n\n"
        f"<b>Title:</b> {escape(title.english_title)}\n"
        f"<b>Published:</b> {published}\n"
        "<b>Formats:</b> PDF + EPUB\n\n"
        "Choose how to open this release."
    )


def render_temporary_ban(
    *, expires_at: datetime, reason: str, timezone_name: str
) -> str:
    local = expires_at.astimezone(ZoneInfo(timezone_name))
    timestamp = local.strftime("%d-%m-%Y %H:%M")
    offset = local.strftime("%z")
    formatted_offset = f"UTC{offset[:3]}:{offset[3:]}" if offset else "UTC"
    return (
        "⛔ <b>ACCOUNT BLOCKED</b>\n\n"
        "Your account is blocked until:\n\n"
        f"<b>{timestamp} {formatted_offset}</b>\n\n"
        f"<b>Reason:</b>\n{escape(reason)}"
    )


def render_permanent_ban(*, reason: str) -> str:
    return (
        "⛔ <b>ACCOUNT PERMANENTLY BLOCKED</b>\n\n"
        "Your account is blocked until the end of time.\n"
        "Unfortunately.\n\n"
        f"<b>Reason:</b>\n{escape(reason)}"
    )
