from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException

from dollartl.admin.auth import validate_telegram_init_data
from dollartl.config import Settings


def make_init_data(token: str, user_id: int) -> str:
    pairs = {
        "auth_date": str(int(datetime.now(timezone.utc).timestamp())),
        "query_id": "AAE-test",
        "user": json.dumps({"id": user_id, "first_name": "Admin"}, separators=(",", ":")),
    }
    check = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


def test_valid_admin_init_data() -> None:
    settings = Settings(telegram_bot_token="token", admin_telegram_id=2096975784)
    assert validate_telegram_init_data(make_init_data("token", 2096975784), settings).telegram_id == 2096975784


def test_other_user_is_rejected() -> None:
    settings = Settings(telegram_bot_token="token", admin_telegram_id=2096975784)
    with pytest.raises(HTTPException) as caught:
        validate_telegram_init_data(make_init_data("token", 1), settings)
    assert caught.value.status_code == 403
