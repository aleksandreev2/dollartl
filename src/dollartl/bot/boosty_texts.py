from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from dollartl.services.boosty import BoostyStatus


def render_status(status: BoostyStatus, timezone_name: str) -> str:
    if status.status == "active_vip":
        return (
            "💎 <b>BOOSTY ACCESS</b>\n\n"
            "Membership status: <b>Active</b>\n"
            "Account status: <b>[VIP]</b>\n"
            f"Boosty account: <b>{escape(status.boosty_username or 'Linked')}</b>\n\n"
            "All available PDF and EPUB releases are unlocked."
        )
    if status.status == "grace_period":
        return (
            "⚠️ <b>BOOSTY GRACE PERIOD</b>\n\n"
            "Your eligible membership could not be confirmed.\n"
            f"Direct access remains available until <b>{_format(status.grace_ends_at, timezone_name)}</b>.\n\n"
            "Renew the membership before this time to keep access."
        )
    if status.status == "expired":
        return (
            "🔒 <b>BOOSTY ACCESS</b>\n\n"
            "Membership status: <b>Inactive</b>\n\n"
            "Direct PDF and EPUB downloads are unavailable. You can still browse titles and open their Boosty publications."
        )
    if status.status == "verification_error":
        return (
            "⚠️ <b>BOOSTY VERIFICATION UNAVAILABLE</b>\n\n"
            "Boosty could not be checked right now. No existing access was removed.\n\n"
            f"Details: {escape(status.last_error_message or 'Temporary API error.')}"
        )
    return (
        "💎 <b>BOOSTY ACCESS</b>\n\n"
        "Connect the supported Boosty membership to unlock all available PDF and EPUB releases, direct protected downloads and [VIP] status."
    )


def render_code(code: str, expires_at: datetime, timezone_name: str) -> str:
    return (
        "🔗 <b>LINK YOUR BOOSTY ACCOUNT</b>\n\n"
        "Send the code below to Dollar TL through Boosty direct messages:\n\n"
        f"<code>{escape(code)}</code>\n\n"
        f"The code expires at <b>{_format(expires_at, timezone_name)}</b>.\n\n"
        "After sending it, return here and tap “Check Status”. Do not share this code with anyone else."
    )


def _format(value: datetime | None, timezone_name: str) -> str:
    if value is None:
        return "Unknown"
    local = value.astimezone(ZoneInfo(timezone_name))
    return local.strftime("%d-%m-%Y %H:%M %Z")
