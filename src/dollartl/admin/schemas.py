from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class TitleCreate(BaseModel):
    english_title: str = Field(min_length=1, max_length=255)
    original_title: str = Field(min_length=1, max_length=255)
    original_language: str = Field(min_length=1, max_length=50)
    publication_status: Literal["ongoing", "completed", "hiatus"] = "ongoing"
    description: str = Field(default="", max_length=20_000)
    boosty_url: str | None = None
    aliases: list[str] = Field(default_factory=list, max_length=30)


class ReleaseCreate(BaseModel):
    title_id: UUID
    chapter_start: int = Field(ge=0)
    chapter_end: int = Field(ge=0)
    display_name: str | None = Field(default=None, max_length=255)
    boosty_url: str | None = None

    @model_validator(mode="after")
    def validate_range(self):
        if self.chapter_end < self.chapter_start:
            raise ValueError("chapter_end must be greater than or equal to chapter_start")
        return self


class ValidationOverride(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


class SuggestionDecision(BaseModel):
    status: Literal["accepted", "rejected", "translated"]
    public_reason: str | None = Field(default=None, max_length=4000)
    internal_note: str | None = Field(default=None, max_length=4000)
    linked_title_id: UUID | None = None


class CommentModeration(BaseModel):
    deleted: bool


class RatingWorkflow(BaseModel):
    status: Literal["new", "reviewed", "in_progress", "fixed", "dismissed"]
    note: str | None = Field(default=None, max_length=4000)


class ReportUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved", "rejected"]
    reply: str | None = Field(default=None, max_length=4000)


class BanCreate(BaseModel):
    ban_type: Literal["temporary", "permanent"]
    public_reason: str = Field(min_length=3, max_length=4000)
    internal_note: str | None = Field(default=None, max_length=4000)
    reason_template: str | None = Field(default=None, max_length=80)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_expiry(self):
        if self.ban_type == "temporary" and self.expires_at is None:
            raise ValueError("expires_at is required for a temporary ban")
        return self


class BroadcastCreate(BaseModel):
    audience_type: Literal["all", "active_vip", "vip_grace", "standard", "title_followers", "selected"]
    text: str = Field(min_length=1, max_length=1024)
    title_id: UUID | None = None
    selected_user_ids: list[UUID] = Field(default_factory=list, max_length=5000)
    button_text: str | None = Field(default=None, max_length=64)
    button_url: str | None = None
    scheduled_at: datetime | None = None
    send_now: bool = False

    @model_validator(mode="after")
    def validate_dependencies(self):
        if self.audience_type == "title_followers" and self.title_id is None:
            raise ValueError("title_id is required for title_followers")
        if self.audience_type == "selected" and not self.selected_user_ids:
            raise ValueError("selected_user_ids is required for selected audience")
        if bool(self.button_text) != bool(self.button_url):
            raise ValueError("button_text and button_url must be provided together")
        return self

    @field_validator("button_url")
    @classmethod
    def validate_button_url(cls, value: str | None) -> str | None:
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("button_url must be an HTTP(S) URL")
        return value


class ChannelSettingsUpdate(BaseModel):
    channel_username: str = Field(min_length=2, max_length=100)
    channel_posts_enabled: bool


class SystemSettingUpdate(BaseModel):
    value: dict
    description: str | None = Field(default=None, max_length=2000)
