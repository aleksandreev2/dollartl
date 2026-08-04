from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException, status

from dollartl.config import Settings, get_settings


@dataclass(frozen=True, slots=True)
class AdminPrincipal:
    telegram_id: int
    username: str | None
    first_name: str | None


def validate_telegram_init_data(init_data: str, settings: Settings) -> AdminPrincipal:
    if not init_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Mini App initData is required")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", "")
    if not received_hash:
        raise HTTPException(status_code=401, detail="initData hash is missing")
    try:
        auth_date = datetime.fromtimestamp(int(pairs.get("auth_date", "")), tz=timezone.utc)
    except (TypeError, ValueError, OSError) as exc:
        raise HTTPException(status_code=401, detail="Invalid initData auth_date") from exc
    age = (datetime.now(timezone.utc) - auth_date).total_seconds()
    if age < -60 or age > settings.admin_init_data_ttl_seconds:
        raise HTTPException(status_code=401, detail="Mini App session expired")
    token = settings.telegram_bot_token.get_secret_value()
    if not token:
        raise HTTPException(status_code=503, detail="Bot token is not configured")
    check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        raise HTTPException(status_code=401, detail="Invalid Mini App signature")
    try:
        user = json.loads(pairs.get("user", "{}"))
        telegram_id = int(user["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Mini App user is missing") from exc
    if telegram_id != settings.admin_telegram_id:
        raise HTTPException(status_code=403, detail="Administrator access required")
    return AdminPrincipal(telegram_id, user.get("username"), user.get("first_name"))


async def require_admin(
    x_telegram_init_data: str = Header(default="", alias="X-Telegram-Init-Data"),
    x_admin_development_id: str = Header(default="", alias="X-Admin-Development-Id"),
) -> AdminPrincipal:
    settings = get_settings()
    if settings.app_env == "development" and x_admin_development_id:
        try:
            telegram_id = int(x_admin_development_id)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid development administrator ID") from exc
        if telegram_id == settings.admin_telegram_id:
            return AdminPrincipal(telegram_id, "development", "Admin")
    return validate_telegram_init_data(x_telegram_init_data, settings)
