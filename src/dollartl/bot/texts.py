from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

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

HOME = """📚 <b>DOLLAR TL</b>

Account: {anonymous_name}

The catalogue, Boosty access and release library will be enabled in the next product updates."""

HELP = """❓ <b>HELP</b>

Use the buttons below to navigate the bot.

System notifications, account restrictions and important rule updates cannot be disabled."""

COMING_SOON = "This section is not available yet."


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
