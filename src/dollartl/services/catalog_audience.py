from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from dollartl.db.models import Title, UserTitleFollow
from dollartl.services.catalog_types import CatalogSessionMixin


class CatalogAudienceMixin(CatalogSessionMixin):
    async def is_following(self, user_id: UUID, title_id: UUID) -> bool:
        return (
            await self.session.execute(
                select(UserTitleFollow.id).where(
                    UserTitleFollow.user_id == user_id,
                    UserTitleFollow.title_id == title_id,
                )
            )
        ).scalar_one_or_none() is not None

    async def toggle_follow(self, user_id: UUID, title_id: UUID) -> bool:
        follow = (
            await self.session.execute(
                select(UserTitleFollow).where(
                    UserTitleFollow.user_id == user_id,
                    UserTitleFollow.title_id == title_id,
                )
            )
        ).scalar_one_or_none()
        if follow is None:
            await self.session.execute(
                insert(UserTitleFollow)
                .values(user_id=user_id, title_id=title_id)
                .on_conflict_do_nothing(
                    index_elements=[UserTitleFollow.user_id, UserTitleFollow.title_id]
                )
            )
            await self.session.commit()
            return True
        await self.session.delete(follow)
        await self.session.commit()
        return False

    async def followed_titles(self, user_id: UUID, *, limit: int = 30) -> list[Title]:
        return list(
            (
                await self.session.execute(
                    select(Title)
                    .join(UserTitleFollow, UserTitleFollow.title_id == Title.id)
                    .where(
                        UserTitleFollow.user_id == user_id,
                        Title.is_published.is_(True),
                    )
                    .order_by(Title.english_title.asc())
                    .limit(limit)
                )
            ).scalars()
        )
