from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from dollartl.config import Settings
from dollartl.db.boosty_models import BoostyCredentialState


@dataclass(frozen=True, slots=True)
class TokenState:
    access_token: str
    refresh_token: str
    expires_at: datetime | None


class BoostyCredentialStore:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def _fernet(self) -> Fernet | None:
        raw = self.settings.boosty_credential_key.get_secret_value().strip()
        return Fernet(raw.encode()) if raw else None

    async def load(self) -> TokenState:
        row = (
            await self.session.execute(
                select(BoostyCredentialState).where(
                    BoostyCredentialState.singleton_key == "primary"
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            fernet = self._fernet()
            if fernet is None:
                raise RuntimeError("BOOSTY_CREDENTIAL_KEY is required to decrypt rotated tokens")
            try:
                decoded = fernet.decrypt(row.encrypted_payload.encode())
            except InvalidToken as exc:
                raise RuntimeError("Stored Boosty credentials cannot be decrypted") from exc
            payload = json.loads(decoded)
            expires_at = _parse_datetime(payload.get("expires_at"))
            return TokenState(
                access_token=str(payload.get("access_token", "")),
                refresh_token=str(payload.get("refresh_token", "")),
                expires_at=expires_at,
            )

        return TokenState(
            access_token=self.settings.boosty_access_token.get_secret_value(),
            refresh_token=self.settings.boosty_refresh_token.get_secret_value(),
            expires_at=None,
        )

    async def save(self, state: TokenState) -> None:
        fernet = self._fernet()
        if fernet is None:
            return
        payload = json.dumps(
            {
                "access_token": state.access_token,
                "refresh_token": state.refresh_token,
                "expires_at": state.expires_at.isoformat() if state.expires_at else None,
            },
            separators=(",", ":"),
        ).encode()
        encrypted = fernet.encrypt(payload).decode()
        now = datetime.now(timezone.utc)
        await self.session.execute(
            insert(BoostyCredentialState)
            .values(
                singleton_key="primary",
                encrypted_payload=encrypted,
                token_expires_at=state.expires_at,
                refreshed_at=now,
            )
            .on_conflict_do_update(
                index_elements=[BoostyCredentialState.singleton_key],
                set_={
                    "encrypted_payload": encrypted,
                    "token_expires_at": state.expires_at,
                    "refreshed_at": now,
                    "updated_at": now,
                },
            )
        )
        await self.session.commit()


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
