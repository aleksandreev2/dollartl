from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class BoostyIdentity:
    user_id: str
    username: str | None = None


@dataclass(frozen=True, slots=True)
class BoostyMembership:
    identity: BoostyIdentity
    tier_id: str | None
    tier_name: str | None
    active: bool
    expires_at: datetime | None = None


class BoostyProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, temporary: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.temporary = temporary


class BoostyProvider(Protocol):
    async def find_verification_codes(
        self, codes: set[str]
    ) -> dict[str, BoostyIdentity]: ...

    async def list_memberships(self) -> dict[str, BoostyMembership]: ...
