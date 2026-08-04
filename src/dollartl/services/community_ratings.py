from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from dollartl.db.models import Release
from dollartl.db.community_models import (
    TranslationRating,
    TranslationRatingCategory,
    TranslationRatingCategoryLink,
    TranslationRatingRevision,
    TranslationRatingStatusHistory,
)
from dollartl.services.community_base import CommunityServiceBase
from dollartl.services.moderation import ModerationService

RATING_STATUSES = {"new", "reviewed", "in_progress", "fixed", "dismissed"}


class CommunityRatingsMixin(CommunityServiceBase):
    async def rating_categories(self) -> dict[str, str]:
        rows = (
            await self.session.execute(
                select(
                    TranslationRatingCategory.code,
                    TranslationRatingCategory.label,
                )
                .where(TranslationRatingCategory.is_active.is_(True))
                .order_by(TranslationRatingCategory.label.asc())
            )
        ).all()
        return {code: label for code, label in rows}

    async def save_rating(
        self,
        *,
        user_id: UUID,
        release_id: UUID,
        score: int,
        category_codes: list[str],
        feedback: str,
    ) -> TranslationRating:
        if score not in {1, 2, 3, 4, 5}:
            raise ValueError("Rating must be between 1 and 5.")
        if not category_codes:
            raise ValueError("Select at least one feedback category.")
        if not 20 <= len(feedback.strip()) <= 2000:
            raise ValueError("Feedback must contain 20–2,000 characters.")
        valid = await self.rating_categories()
        selected = list(dict.fromkeys(category_codes))
        if any(code not in valid for code in selected):
            raise ValueError("Unknown feedback category.")
        if score < 5 and "no_issues" in selected:
            raise ValueError("Choose a problem category for ratings below 5.")
        _, vip = await self.display_name(user_id)
        sanitized = await ModerationService(self.session).sanitize(
            user_id=user_id,
            text=feedback.strip(),
            surface="feedback",
            entity_type="release",
            entity_id=str(release_id),
        )
        rating = (
            await self.session.execute(
                select(TranslationRating).where(
                    TranslationRating.user_id == user_id,
                    TranslationRating.release_id == release_id,
                )
            )
        ).scalar_one_or_none()
        if rating is None:
            rating = TranslationRating(
                user_id=user_id,
                release_id=release_id,
                score=score,
                feedback=sanitized.text,
                vip_snapshot=vip,
                status="new",
            )
            self.session.add(rating)
            await self.session.flush()
        else:
            old_codes = await self._category_codes(rating.id)
            self.session.add(
                TranslationRatingRevision(
                    rating_id=rating.id,
                    score=rating.score,
                    feedback=rating.feedback,
                    category_codes=old_codes,
                    vip_snapshot=rating.vip_snapshot,
                )
            )
            rating.score = score
            rating.feedback = sanitized.text
            rating.vip_snapshot = vip
            rating.status = "new"
            rating.is_deleted = False
            await self.session.execute(
                delete(TranslationRatingCategoryLink).where(
                    TranslationRatingCategoryLink.rating_id == rating.id
                )
            )
        categories = list(
            (
                await self.session.execute(
                    select(TranslationRatingCategory).where(
                        TranslationRatingCategory.code.in_(selected)
                    )
                )
            ).scalars()
        )
        for category in categories:
            await self.session.execute(
                insert(TranslationRatingCategoryLink)
                .values(rating_id=rating.id, category_id=category.id)
                .on_conflict_do_nothing(
                    index_elements=[
                        TranslationRatingCategoryLink.rating_id,
                        TranslationRatingCategoryLink.category_id,
                    ]
                )
            )
        await self.session.commit()
        return rating

    async def rating_summary(self, release_id: UUID) -> tuple[float | None, int]:
        average, count = (
            await self.session.execute(
                select(
                    func.avg(TranslationRating.score),
                    func.count(TranslationRating.id),
                ).where(
                    TranslationRating.release_id == release_id,
                    TranslationRating.is_deleted.is_(False),
                )
            )
        ).one()
        return (round(float(average), 2) if average is not None else None, int(count))

    async def title_rating_summary(self, title_id: UUID) -> tuple[float | None, int]:
        average, count = (
            await self.session.execute(
                select(
                    func.avg(TranslationRating.score),
                    func.count(TranslationRating.id),
                )
                .join(Release, Release.id == TranslationRating.release_id)
                .where(
                    Release.title_id == title_id,
                    TranslationRating.is_deleted.is_(False),
                )
            )
        ).one()
        return (round(float(average), 2) if average is not None else None, int(count))

    async def set_rating_status(
        self,
        rating_id: UUID,
        *,
        status: str,
        admin_telegram_id: int,
        note: str | None = None,
    ) -> bool:
        if status not in RATING_STATUSES:
            raise ValueError("Unknown rating status.")
        rating = await self.session.get(TranslationRating, rating_id)
        if rating is None:
            return False
        old_status = rating.status
        rating.status = status
        self.session.add(
            TranslationRatingStatusHistory(
                rating_id=rating.id,
                old_status=old_status,
                new_status=status,
                admin_telegram_id=admin_telegram_id,
                note=note,
            )
        )
        await self.session.commit()
        return True

    async def _category_codes(self, rating_id: UUID) -> list[str]:
        return list(
            (
                await self.session.execute(
                    select(TranslationRatingCategory.code)
                    .join(
                        TranslationRatingCategoryLink,
                        TranslationRatingCategoryLink.category_id
                        == TranslationRatingCategory.id,
                    )
                    .where(TranslationRatingCategoryLink.rating_id == rating_id)
                )
            ).scalars()
        )
