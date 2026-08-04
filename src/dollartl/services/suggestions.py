from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from dollartl.config import Settings
from dollartl.db.models import AuditLog, Title, User
from dollartl.db.suggestion_models import (
    DuplicateCandidate,
    SuggestionFile,
    SuggestionQuotaUsage,
    SuggestionRuleConsent,
    SuggestionSource,
    SuggestionStatusHistory,
    TitleSuggestion,
)
from dollartl.services.boosty import BoostyService
from dollartl.services.suggestion_helpers import detect_title_language, normalize_title, quota_limit, quota_month, requested_scope

PUBLIC_STATUS = {
    "under_review": "Under Review",
    "accepted": "Accepted",
    "translated": "Translated",
    "rejected": "Rejected",
    "draft": "Draft",
}


@dataclass(frozen=True, slots=True)
class SuggestionDetails:
    suggestion: TitleSuggestion
    sources: list[SuggestionSource]
    files: list[SuggestionFile]


@dataclass(frozen=True, slots=True)
class QuotaSnapshot:
    used: int
    limit: int
    vip: bool

    @property
    def remaining(self) -> int:
        return max(self.limit - self.used, 0)


class SuggestionService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def has_rules_consent(self, user_id: UUID) -> bool:
        return (
            await self.session.execute(
                select(SuggestionRuleConsent.id).where(
                    SuggestionRuleConsent.user_id == user_id,
                    SuggestionRuleConsent.version == self.settings.suggestion_rules_version,
                )
            )
        ).scalar_one_or_none() is not None

    async def accept_rules(self, user_id: UUID) -> None:
        await self.session.execute(
            insert(SuggestionRuleConsent)
            .values(user_id=user_id, version=self.settings.suggestion_rules_version)
            .on_conflict_do_nothing(
                index_elements=[SuggestionRuleConsent.user_id, SuggestionRuleConsent.version]
            )
        )
        await self.session.commit()

    async def quota_snapshot(self, user: User) -> QuotaSnapshot:
        status = await BoostyService(self.session, self.settings).get_status(user.id)
        vip = status.has_download_access
        limit = quota_limit(
            vip=vip,
            standard_limit=self.settings.suggestion_standard_monthly_limit,
            vip_limit=self.settings.suggestion_vip_monthly_limit,
            administrator=user.telegram_id == self.settings.admin_telegram_id,
        )
        used = int(
            (
                await self.session.execute(
                    select(func.count(SuggestionQuotaUsage.id)).where(
                        SuggestionQuotaUsage.user_id == user.id,
                        SuggestionQuotaUsage.quota_month == quota_month(),
                        SuggestionQuotaUsage.restored_at.is_(None),
                    )
                )
            ).scalar_one()
        )
        return QuotaSnapshot(used=used, limit=limit, vip=vip)

    async def get_or_create_draft(self, user: User) -> TitleSuggestion:
        draft = (
            await self.session.execute(
                select(TitleSuggestion)
                .where(TitleSuggestion.user_id == user.id, TitleSuggestion.status == "draft")
                .order_by(TitleSuggestion.updated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if draft is not None:
            return draft
        status = await BoostyService(self.session, self.settings).get_status(user.id)
        draft = TitleSuggestion(user_id=user.id, status="draft", vip_snapshot=status.has_download_access)
        self.session.add(draft)
        await self.session.commit()
        return draft

    async def set_title(self, suggestion_id: UUID, value: str) -> TitleSuggestion:
        title = value.strip()
        if len(title) < 2 or len(title) > 500:
            raise ValueError("The original title must be between 2 and 500 characters.")
        suggestion = await self._draft(suggestion_id)
        suggestion.original_title = title
        suggestion.normalized_title = normalize_title(title)
        suggestion.detected_language = detect_title_language(title)
        await self.session.commit()
        return suggestion

    async def set_sources(self, suggestion_id: UUID, sources: list[tuple[str, str]]) -> None:
        suggestion = await self._draft(suggestion_id)
        existing = list(
            (
                await self.session.execute(
                    select(SuggestionSource).where(SuggestionSource.suggestion_id == suggestion.id)
                )
            ).scalars()
        )
        for item in existing:
            await self.session.delete(item)
        for index, (url, normalized) in enumerate(sources):
            self.session.add(
                SuggestionSource(
                    suggestion_id=suggestion.id,
                    url=url,
                    normalized_url=normalized,
                    source_order=index,
                )
            )
        await self.session.commit()

    async def set_chapter_count(self, suggestion_id: UUID, chapter_count: int) -> None:
        if chapter_count < 1 or chapter_count > 1_000_000:
            raise ValueError("Chapter count must be between 1 and 1,000,000.")
        suggestion = await self._draft(suggestion_id)
        suggestion.chapter_count = chapter_count
        await self.session.commit()

    async def set_publication_status(self, suggestion_id: UUID, status: str) -> None:
        if status not in {"ongoing", "completed", "hiatus", "unknown"}:
            raise ValueError("Unsupported publication status.")
        suggestion = await self._draft(suggestion_id)
        suggestion.publication_status = status
        await self.session.commit()

    async def attach_file(
        self,
        *,
        suggestion_id: UUID,
        file_kind: str,
        object_key: str,
        original_filename: str,
        content_type: str,
        size_bytes: int,
        sha256: str,
        telegram_file_id: str | None,
        telegram_file_unique_id: str | None,
        validation_status: str,
        validation_message: str,
        inspection: dict[str, object],
    ) -> SuggestionFile:
        suggestion = await self._draft(suggestion_id)
        existing = (
            await self.session.execute(
                select(SuggestionFile).where(
                    SuggestionFile.suggestion_id == suggestion.id,
                    SuggestionFile.file_kind == file_kind,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = SuggestionFile(suggestion_id=suggestion.id, file_kind=file_kind, object_key=object_key)
            self.session.add(existing)
        existing.object_key = object_key
        existing.original_filename = original_filename
        existing.content_type = content_type
        existing.size_bytes = size_bytes
        existing.sha256 = sha256
        existing.telegram_file_id = telegram_file_id
        existing.telegram_file_unique_id = telegram_file_unique_id
        existing.validation_status = validation_status
        existing.validation_message = validation_message
        existing.inspection = inspection
        await self.session.commit()
        return existing

    async def review(self, suggestion_id: UUID) -> SuggestionDetails:
        suggestion = await self.session.get(TitleSuggestion, suggestion_id)
        if suggestion is None:
            raise ValueError("Suggestion could not be found.")
        sources = list(
            (
                await self.session.execute(
                    select(SuggestionSource)
                    .where(SuggestionSource.suggestion_id == suggestion.id)
                    .order_by(SuggestionSource.source_order)
                )
            ).scalars()
        )
        files = list(
            (
                await self.session.execute(
                    select(SuggestionFile).where(SuggestionFile.suggestion_id == suggestion.id)
                )
            ).scalars()
        )
        return SuggestionDetails(suggestion=suggestion, sources=sources, files=files)

    async def submit(self, suggestion_id: UUID, user: User) -> TitleSuggestion:
        suggestion = await self._draft(suggestion_id)
        if not suggestion.original_title or not suggestion.normalized_title:
            raise ValueError("Original title is missing.")
        if suggestion.chapter_count is None or suggestion.publication_status is None:
            raise ValueError("Chapter count or publication status is missing.")
        source_count = int(
            (
                await self.session.execute(
                    select(func.count(SuggestionSource.id)).where(
                        SuggestionSource.suggestion_id == suggestion.id
                    )
                )
            ).scalar_one()
        )
        if source_count < 1:
            raise ValueError("At least one source is required.")

        persisted_user = (
            await self.session.execute(
                select(User).where(User.id == user.id).with_for_update()
            )
        ).scalar_one()
        quota = await self.quota_snapshot(persisted_user)
        if quota.used >= quota.limit:
            raise ValueError("Your title suggestion quota for this calendar month has been used.")
        administrator = persisted_user.telegram_id == self.settings.admin_telegram_id
        start, end = requested_scope(
            chapter_count=suggestion.chapter_count,
            vip=quota.vip,
            standard_cap=self.settings.suggestion_standard_chapter_limit,
            administrator=administrator,
        )
        suggestion.requested_chapter_start = start
        suggestion.requested_chapter_end = end
        suggestion.vip_snapshot = quota.vip
        suggestion.status = "under_review"
        suggestion.submitted_at = datetime.now(timezone.utc)
        await self._detect_duplicates(suggestion)
        self.session.add(
            SuggestionQuotaUsage(
                user_id=persisted_user.id,
                suggestion_id=suggestion.id,
                quota_month=quota_month(),
            )
        )
        self.session.add(
            SuggestionStatusHistory(
                suggestion_id=suggestion.id,
                from_status="draft",
                to_status="under_review",
                actor_user_id=persisted_user.id,
            )
        )
        self.session.add(
            AuditLog(
                actor_telegram_id=persisted_user.telegram_id,
                action="suggestion.submitted",
                entity_type="title_suggestion",
                entity_id=str(suggestion.id),
                payload={"vip": quota.vip, "scope_end": end},
            )
        )
        await self.session.commit()
        return suggestion

    async def list_user(self, user_id: UUID, limit: int = 20) -> list[TitleSuggestion]:
        return list(
            (
                await self.session.execute(
                    select(TitleSuggestion)
                    .where(TitleSuggestion.user_id == user_id, TitleSuggestion.status != "draft")
                    .order_by(TitleSuggestion.submitted_at.desc())
                    .limit(limit)
                )
            ).scalars()
        )

    async def list_admin(self, status: str = "under_review", limit: int = 30) -> list[TitleSuggestion]:
        statement = select(TitleSuggestion).where(TitleSuggestion.status != "draft")
        if status != "all":
            statement = statement.where(TitleSuggestion.status == status)
        return list((await self.session.execute(statement.order_by(TitleSuggestion.submitted_at.asc()).limit(limit))).scalars())

    async def get(self, suggestion_id: UUID) -> TitleSuggestion | None:
        return await self.session.get(TitleSuggestion, suggestion_id)

    async def change_status(
        self,
        *,
        suggestion: TitleSuggestion,
        new_status: str,
        admin_telegram_id: int,
        public_reason: str | None = None,
        internal_note: str | None = None,
        linked_title_id: UUID | None = None,
    ) -> None:
        if new_status not in {"accepted", "translated", "rejected"}:
            raise ValueError("Unsupported suggestion status.")
        if new_status == "rejected" and not (public_reason or "").strip():
            raise ValueError("A public rejection reason is required.")
        if new_status == "translated":
            linked_title = (
                await self.session.get(Title, linked_title_id)
                if linked_title_id is not None
                else None
            )
            if linked_title is None or not linked_title.is_published:
                raise ValueError(
                    "Translated suggestions require a valid published title UUID."
                )
        old = suggestion.status
        suggestion.status = new_status
        suggestion.public_reason = (public_reason or "").strip() or None
        suggestion.internal_note = (internal_note or "").strip() or None
        suggestion.linked_title_id = linked_title_id if new_status == "translated" else suggestion.linked_title_id
        suggestion.decided_at = datetime.now(timezone.utc)
        self.session.add(
            SuggestionStatusHistory(
                suggestion_id=suggestion.id,
                from_status=old,
                to_status=new_status,
                public_reason=suggestion.public_reason,
                internal_note=suggestion.internal_note,
                actor_admin_id=admin_telegram_id,
            )
        )
        self.session.add(
            AuditLog(
                actor_telegram_id=admin_telegram_id,
                action="suggestion.status_changed",
                entity_type="title_suggestion",
                entity_id=str(suggestion.id),
                payload={"from": old, "to": new_status},
            )
        )
        await self.session.commit()

    async def restore_quota_slot(self, suggestion_id: UUID, admin_id: int, reason: str) -> bool:
        usage = (
            await self.session.execute(
                select(SuggestionQuotaUsage).where(
                    SuggestionQuotaUsage.suggestion_id == suggestion_id,
                    SuggestionQuotaUsage.restored_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if usage is None:
            return False
        usage.restored_at = datetime.now(timezone.utc)
        usage.restored_by_admin_id = admin_id
        usage.restore_reason = reason.strip() or "Administrative restoration"
        await self.session.commit()
        return True

    async def _draft(self, suggestion_id: UUID) -> TitleSuggestion:
        suggestion = await self.session.get(TitleSuggestion, suggestion_id)
        if suggestion is None or suggestion.status != "draft":
            raise ValueError("Suggestion draft is no longer available.")
        return suggestion

    async def _detect_duplicates(self, suggestion: TitleSuggestion) -> None:
        matches = list(
            (
                await self.session.execute(
                    select(TitleSuggestion).where(
                        TitleSuggestion.id != suggestion.id,
                        TitleSuggestion.normalized_title == suggestion.normalized_title,
                        TitleSuggestion.status != "draft",
                    )
                )
            ).scalars()
        )
        source_urls = list(
            (
                await self.session.execute(
                    select(SuggestionSource.normalized_url).where(
                        SuggestionSource.suggestion_id == suggestion.id
                    )
                )
            ).scalars()
        )
        if source_urls:
            source_matches = list(
                (
                    await self.session.execute(
                        select(TitleSuggestion)
                        .join(SuggestionSource, SuggestionSource.suggestion_id == TitleSuggestion.id)
                        .where(
                            TitleSuggestion.id != suggestion.id,
                            TitleSuggestion.status != "draft",
                            SuggestionSource.normalized_url.in_(source_urls),
                        )
                        .distinct()
                    )
                ).scalars()
            )
            matches.extend(source_matches)
        file_hashes = list(
            (
                await self.session.execute(
                    select(SuggestionFile.sha256).where(SuggestionFile.suggestion_id == suggestion.id)
                )
            ).scalars()
        )
        if file_hashes:
            file_matches = list(
                (
                    await self.session.execute(
                        select(TitleSuggestion)
                        .join(SuggestionFile, SuggestionFile.suggestion_id == TitleSuggestion.id)
                        .where(
                            TitleSuggestion.id != suggestion.id,
                            TitleSuggestion.status != "draft",
                            SuggestionFile.sha256.in_(file_hashes),
                        )
                        .distinct()
                    )
                ).scalars()
            )
            matches.extend(file_matches)
        unique = {item.id: item for item in matches}
        published_titles = list(
            (await self.session.execute(select(Title).where(Title.is_published.is_(True)))).scalars()
        )
        for title in published_titles:
            if normalize_title(title.original_title) == suggestion.normalized_title or normalize_title(title.english_title) == suggestion.normalized_title:
                self.session.add(
                    DuplicateCandidate(
                        suggestion_id=suggestion.id,
                        candidate_type="published_title",
                        candidate_title_id=title.id,
                        reason="The title matches an already published work.",
                        score=100,
                    )
                )
                suggestion.duplicate_review_required = True
        for candidate in unique.values():
            self.session.add(
                DuplicateCandidate(
                    suggestion_id=suggestion.id,
                    candidate_type="suggestion",
                    candidate_suggestion_id=candidate.id,
                    reason="Exact title, source URL or file checksum match.",
                    score=100,
                )
            )
        if unique:
            suggestion.duplicate_review_required = True
