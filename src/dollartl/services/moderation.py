from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dollartl.db.community_models import (
    ModerationAllowlist,
    ModerationMatch,
    ModerationRule,
)

URL_RE = re.compile(r"(?:https?://|t\.me/|www\.)", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")

FALLBACK_RULES: tuple[tuple[str, str, str], ...] = (
    (
        "nword",
        "racist_slur",
        r"(?i)(?<![a-z0-9])n[\W_]*[i1!|][\W_]*[g69q][\W_]*[g69q][\W_]*[e3][\W_]*r?s?(?![a-z0-9])",
    ),
    (
        "racist_slur_2",
        "racist_slur",
        r"(?i)(?<![a-z0-9])c[\W_]*h[\W_]*[i1][\W_]*n[\W_]*k(?![a-z0-9])",
    ),
)


@dataclass(frozen=True, slots=True)
class ModerationResult:
    text: str
    replacements: int
    categories: tuple[str, ...]
    nword_detected: bool


def normalize_for_matching(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.translate(
        str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t"})
    )
    return WHITESPACE_RE.sub(" ", normalized).strip()


class ModerationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def sanitize(
        self,
        *,
        user_id: UUID,
        text: str,
        surface: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> ModerationResult:
        rules = await self._rules(surface)
        allowlist = {
            row
            for row in (
                await self.session.execute(
                    select(ModerationAllowlist.normalized_value).where(
                        ModerationAllowlist.is_active.is_(True)
                    )
                )
            ).scalars()
        }
        normalized = normalize_for_matching(text)
        if normalized in allowlist:
            return ModerationResult(text=text, replacements=0, categories=(), nword_detected=False)

        output = text
        replacements = 0
        categories: set[str] = set()
        nword = False
        for rule_id, code, category, pattern, replacement in rules:
            regex = re.compile(pattern)
            matches = list(regex.finditer(output))
            if not matches:
                continue
            categories.add(category)
            nword = nword or code == "nword"
            replacements += len(matches)
            for match in matches:
                self.session.add(
                    ModerationMatch(
                        user_id=user_id,
                        rule_id=rule_id,
                        surface=surface,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        matched_hash=hashlib.sha256(
                            match.group(0).casefold().encode("utf-8")
                        ).hexdigest(),
                        metadata_json={"rule_code": code, "category": category},
                    )
                )
            output = regex.sub(replacement, output)
        return ModerationResult(
            text=output,
            replacements=replacements,
            categories=tuple(sorted(categories)),
            nword_detected=nword,
        )

    async def validate_nickname(self, *, user_id: UUID, nickname: str) -> tuple[str, bool]:
        candidate = WHITESPACE_RE.sub(" ", nickname.strip())
        if not 3 <= len(candidate) <= 24:
            raise ValueError("Nickname must contain 3–24 characters.")
        if URL_RE.search(candidate):
            raise ValueError("Advertising links are not allowed in nicknames.")
        result = await self.sanitize(user_id=user_id, text=candidate, surface="nickname")
        if result.replacements:
            await self.session.commit()
            if result.nword_detected:
                return candidate, True
            raise ValueError(
                "Bro, that nickname isn't happening. Pick something without racist garbage."
            )
        return candidate, False

    async def _rules(
        self, surface: str
    ) -> list[tuple[UUID | None, str, str, str, str]]:
        column = {
            "comment": ModerationRule.applies_to_comments,
            "nickname": ModerationRule.applies_to_nicknames,
            "feedback": ModerationRule.applies_to_feedback,
            "report": ModerationRule.applies_to_feedback,
        }.get(surface, ModerationRule.applies_to_comments)
        rows = list(
            (
                await self.session.execute(
                    select(ModerationRule).where(
                        ModerationRule.is_active.is_(True), column.is_(True)
                    )
                )
            ).scalars()
        )
        if rows:
            return [
                (row.id, row.code, row.category, row.pattern, row.replacement)
                for row in rows
            ]
        return [
            (None, code, category, pattern, "***")
            for code, category, pattern in FALLBACK_RULES
        ]
