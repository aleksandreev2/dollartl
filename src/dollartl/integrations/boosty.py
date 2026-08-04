from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from dollartl.config import Settings
from dollartl.integrations.boosty_credentials import BoostyCredentialStore, TokenState
from dollartl.integrations.boosty_types import (
    BoostyIdentity,
    BoostyMembership,
    BoostyProviderError,
)


class PrivateBoostyProvider:
    """Adapter around Boosty's undocumented web API.

    Response parsing is intentionally defensive because the private API is not a stable contract.
    """

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.settings = settings
        self.credentials = BoostyCredentialStore(session, settings)
        self.client = httpx.AsyncClient(
            base_url=settings.boosty_api_base_url.rstrip("/"),
            timeout=settings.boosty_request_timeout_seconds,
            follow_redirects=True,
        )
        self._tokens: TokenState | None = None

    async def __aenter__(self) -> PrivateBoostyProvider:
        self._tokens = await self.credentials.load()
        if not self._tokens.access_token and not self._tokens.refresh_token:
            raise BoostyProviderError(
                "credentials_missing",
                "Boosty credentials are not configured.",
                temporary=False,
            )
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.client.aclose()

    def _headers(self) -> dict[str, str]:
        token = self._tokens.access_token if self._tokens else ""
        return {
            "Authorization": f"Bearer {token}",
            "X-Currency": "RUB",
            "X-Locale": "ru_RU",
            "X-App": "web",
            "User-Agent": "Mozilla/5.0 DollarTLBot/0.4",
            "Accept": "application/json",
        }

    async def _ensure_fresh_token(self) -> None:
        if self._tokens is None:
            self._tokens = await self.credentials.load()
        expires_at = self._tokens.expires_at
        if expires_at is not None and expires_at <= datetime.now(timezone.utc) + timedelta(minutes=5):
            await self._refresh_tokens()

    async def _refresh_tokens(self) -> None:
        if self._tokens is None:
            self._tokens = await self.credentials.load()
        if not self._tokens.refresh_token:
            raise BoostyProviderError(
                "refresh_token_missing", "Boosty refresh token is not configured.", temporary=False
            )
        response = await self.client.post(
            "/oauth/token/",
            data={
                "device_id": self.settings.boosty_device_id.get_secret_value(),
                "device_os": "web",
                "grant_type": "refresh_token",
                "refresh_token": self._tokens.refresh_token,
            },
            headers={
                "Authorization": f"Bearer {self._tokens.access_token}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 DollarTLBot/0.4",
            },
        )
        if response.status_code != 200:
            raise BoostyProviderError(
                "token_refresh_failed",
                f"Boosty token refresh returned HTTP {response.status_code}.",
                temporary=response.status_code >= 500 or response.status_code == 429,
            )
        payload = response.json()
        access_token = str(payload.get("access_token") or payload.get("accessToken") or "")
        refresh_token = str(
            payload.get("refresh_token") or payload.get("refreshToken") or self._tokens.refresh_token
        )
        if not access_token:
            raise BoostyProviderError(
                "token_refresh_invalid", "Boosty token refresh returned no access token."
            )
        expires_in = _as_int(payload.get("expires_in") or payload.get("expiresIn")) or 604800
        self._tokens = TokenState(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        )
        await self.credentials.save(self._tokens)

    async def _request_json(
        self, method: str, path: str, *, params: dict[str, object] | None = None
    ) -> Any:
        await self._ensure_fresh_token()
        response = await self.client.request(method, path, params=params, headers=self._headers())
        if response.status_code == 401 and self._tokens and self._tokens.refresh_token:
            await self._refresh_tokens()
            response = await self.client.request(method, path, params=params, headers=self._headers())
        if response.status_code == 429:
            raise BoostyProviderError("rate_limited", "Boosty rate limit reached.")
        if response.status_code >= 500:
            raise BoostyProviderError(
                "boosty_unavailable", f"Boosty returned HTTP {response.status_code}."
            )
        if response.status_code >= 400:
            raise BoostyProviderError(
                "boosty_request_failed",
                f"Boosty returned HTTP {response.status_code} for {path}.",
                temporary=response.status_code in {408, 409, 425},
            )
        try:
            return response.json()
        except ValueError as exc:
            raise BoostyProviderError(
                "invalid_json", f"Boosty returned invalid JSON for {path}."
            ) from exc

    async def find_verification_codes(
        self, codes: set[str]
    ) -> dict[str, BoostyIdentity]:
        normalized = {code.upper(): code for code in codes if code}
        if not normalized:
            return {}
        payload = await self._request_json(
            "GET",
            "/v1/dialog/contacts",
            params={
                "limit": self.settings.boosty_contacts_limit,
                "sort_by": "name",
                "sort_order": "asc",
            },
        )
        matches: dict[str, BoostyIdentity] = {}
        contacts = _list_items(payload)
        for contact in contacts:
            identity = _extract_identity(contact)
            if identity is None:
                continue
            for code in normalized:
                if _payload_contains_code(contact, code):
                    matches[normalized[code]] = identity
            remaining = set(normalized.values()) - set(matches)
            if not remaining:
                break
            dialog = await self._request_json(
                "GET", "/v1/dialog", params={"user_id": identity.user_id}
            )
            for code_upper, original in normalized.items():
                if original not in matches and _payload_contains_code(dialog, code_upper):
                    matches[original] = identity
        return matches

    async def list_memberships(self) -> dict[str, BoostyMembership]:
        memberships: dict[str, BoostyMembership] = {}
        limit = self.settings.boosty_subscribers_page_size
        offset = 0
        seen_page_ids: set[str] = set()
        for _ in range(self.settings.boosty_max_subscriber_pages):
            payload = await self._request_json(
                "GET",
                f"/v1/blog/{self.settings.boosty_blog_name}/subscribers",
                params={
                    "sort_by": "on_time",
                    "limit": limit,
                    "offset": offset,
                    "order": "gt",
                },
            )
            items = _list_items(payload)
            page_ids = {
                identity.user_id
                for item in items
                if (identity := _extract_identity(item)) is not None
            }
            new_page_ids = page_ids - seen_page_ids
            if items and not new_page_ids:
                break
            seen_page_ids.update(page_ids)
            for item in items:
                membership = _extract_membership(item)
                if membership is None:
                    continue
                previous = memberships.get(membership.identity.user_id)
                if previous is None or (membership.active and not previous.active):
                    memberships[membership.identity.user_id] = membership
                elif (
                    previous.tier_id != self.settings.boosty_tier_id
                    and membership.tier_id == self.settings.boosty_tier_id
                ):
                    memberships[membership.identity.user_id] = membership
            if len(items) < limit:
                break
            offset += len(items)
        return memberships


def _walk(value: object) -> Iterator[object]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _list_items(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "items", "list", "subscribers", "contacts", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _list_items(value)
            if nested:
                return nested
    return [payload]


def _payload_contains_code(payload: object, code_upper: str) -> bool:
    for item in _walk(payload):
        if isinstance(item, str) and code_upper in item.upper():
            return True
    return False


def _extract_identity(payload: dict[str, Any]) -> BoostyIdentity | None:
    candidates: list[dict[str, Any]] = [payload]
    for key in ("user", "owner", "subscriber", "contact", "author"):
        value = payload.get(key)
        if isinstance(value, dict):
            candidates.insert(0, value)
    for item in candidates:
        user_id = _first_value(item, ("userId", "user_id", "id", "intId", "int_id"))
        if user_id is None:
            continue
        username = _first_value(
            item, ("username", "name", "nick", "nickname", "blogUrl", "blog_url", "href")
        )
        return BoostyIdentity(user_id=str(user_id), username=str(username) if username else None)
    return None


def _extract_membership(payload: dict[str, Any]) -> BoostyMembership | None:
    identity = _extract_identity(payload)
    if identity is None:
        return None
    tier_id: str | None = None
    tier_name: str | None = None
    for key in ("subscriptionLevel", "subscription_level", "level", "tier"):
        level = payload.get(key)
        if isinstance(level, dict):
            raw_id = _first_value(level, ("id", "levelId", "level_id", "externalId"))
            raw_name = _first_value(level, ("name", "title"))
            if raw_id is not None:
                tier_id = str(raw_id)
            if raw_name is not None:
                tier_name = str(raw_name)
            break
    if tier_id is None:
        raw_id = _first_value(
            payload,
            ("subscriptionLevelId", "subscription_level_id", "levelId", "level_id", "tierId"),
        )
        if raw_id is not None:
            tier_id = str(raw_id)
    active_raw = _first_value(payload, ("isActive", "is_active", "active", "subscribed"))
    status_raw = str(_first_value(payload, ("status", "state")) or "").casefold()
    parsed_active = _as_bool(active_raw)
    active = parsed_active if parsed_active is not None else status_raw not in {
        "expired",
        "cancelled",
        "canceled",
        "inactive",
        "deleted",
    }
    expires_at = _parse_timestamp(
        _first_value(payload, ("expiresAt", "expires_at", "subscriptionExpiresAt", "subscription_expires_at"))
    )
    if expires_at is not None and expires_at <= datetime.now(timezone.utc):
        active = False
    return BoostyMembership(
        identity=identity,
        tier_id=tier_id,
        tier_name=tier_name,
        active=active,
        expires_at=expires_at,
    )


def _first_value(payload: dict[str, Any], keys: Iterable[str]) -> object | None:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def _as_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes", "active"}:
            return True
        if normalized in {"false", "0", "no", "inactive", "expired"}:
            return False
    return None


def _as_int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _parse_timestamp(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) or str(value).isdigit():
        raw = float(value)
        if raw > 10_000_000_000:
            raw /= 1000
        return datetime.fromtimestamp(raw, tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
