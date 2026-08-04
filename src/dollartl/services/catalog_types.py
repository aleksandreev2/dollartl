from __future__ import annotations

import re
import secrets
import unicodedata
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from dollartl.db.models import FileVersion, Release, ReleaseFile, Title

ALLOWED_DEEP_TOKEN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_SLUG_NON_WORD = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class DeepLinkTarget:
    target_type: str
    title_id: UUID | None = None
    release_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ReleaseFileBundle:
    release_file: ReleaseFile
    version: FileVersion


class CatalogSessionMixin:
    session: AsyncSession

    async def get_current_file_versions(
        self, release_id: UUID
    ) -> list[ReleaseFileBundle]:
        raise NotImplementedError

    async def title_for_release(self, release: Release) -> Title:
        raise NotImplementedError


def normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join("".join(char if char.isalnum() else " " for char in normalized).split())


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = _SLUG_NON_WORD.sub("-", normalized.casefold()).strip("-")
    return slug[:80] or "title"


def generate_deep_link_token() -> str:
    token = secrets.token_urlsafe(12).rstrip("=")
    if not ALLOWED_DEEP_TOKEN.fullmatch(token):
        raise RuntimeError("Generated invalid deep-link token")
    return token
