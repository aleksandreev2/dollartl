from __future__ import annotations

import math
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import exists, or_, select

from dollartl.admin.auth import AdminPrincipal, require_admin
from dollartl.db.models import Ban, User

Admin = Annotated[AdminPrincipal, Depends(require_admin)]

_ALLOWED_BATCH_ACTIONS: dict[str, set[str]] = {
    "comments": {"delete", "restore"},
    "ratings": {"new", "reviewed", "in_progress", "fixed", "dismissed"},
    "reports": {"open", "in_progress", "resolved", "rejected"},
}


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def page_meta(*, total: int, page: int, page_size: int) -> dict[str, int]:
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": max(1, math.ceil(total / page_size)),
    }


def active_ban_exists(now: datetime) -> Any:
    return exists(
        select(Ban.id).where(
            Ban.user_id == User.id,
            Ban.is_active.is_(True),
            or_(
                Ban.ban_type == "permanent",
                Ban.expires_at.is_(None),
                Ban.expires_at > now,
            ),
        )
    )


class SelectedUsersRequest(BaseModel):
    user_ids: list[UUID] = Field(min_length=1, max_length=5000)


class BatchModerationRequest(BaseModel):
    kind: Literal["comments", "ratings", "reports"]
    ids: list[UUID] = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=40)
    note: str | None = Field(default=None, max_length=2000)
    dry_run: bool = True
    idempotency_key: str = Field(
        min_length=12,
        max_length=120,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )

    @model_validator(mode="after")
    def validate_action(self) -> "BatchModerationRequest":
        if self.action not in _ALLOWED_BATCH_ACTIONS[self.kind]:
            raise ValueError(f"Unsupported action for {self.kind}: {self.action}")
        if len(set(self.ids)) != len(self.ids):
            raise ValueError("Duplicate entity IDs are not allowed")
        return self
