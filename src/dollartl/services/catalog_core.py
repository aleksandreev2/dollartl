from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select

from dollartl.db.models import AuditLog, Release, Title, TitleAlias
from dollartl.services.catalog_types import CatalogSessionMixin, normalize_title, slugify


class CatalogCoreMixin(CatalogSessionMixin):
    async def create_title(
        self,
        *,
        english_title: str,
        original_title: str,
        original_language: str,
        publication_status: str,
        boosty_url: str | None,
        admin_telegram_id: int,
        description: str = "",
        aliases: list[str] | None = None,
    ) -> Title:
        if publication_status not in {"ongoing", "completed", "hiatus"}:
            raise ValueError("Status must be ongoing, completed or hiatus")
        base_slug = slugify(english_title)
        slug = base_slug
        suffix = 2
        while (
            await self.session.execute(select(Title.id).where(Title.slug == slug))
        ).scalar_one_or_none() is not None:
            slug = f"{base_slug[:72]}-{suffix}"
            suffix += 1

        title = Title(
            slug=slug,
            english_title=english_title.strip(),
            original_title=original_title.strip(),
            original_language=original_language.strip(),
            publication_status=publication_status,
            boosty_url=boosty_url,
            description=description.strip(),
            created_by_admin_id=admin_telegram_id,
        )
        self.session.add(title)
        await self.session.flush()

        alias_values = {english_title, original_title, *(aliases or [])}
        unique_aliases: dict[str, str] = {}
        for value in alias_values:
            alias = value.strip()
            normalized_alias = normalize_title(alias)
            if alias and normalized_alias:
                unique_aliases.setdefault(normalized_alias, alias)
        for normalized_alias, alias in sorted(unique_aliases.items()):
            self.session.add(
                TitleAlias(
                    title_id=title.id,
                    alias=alias,
                    normalized_alias=normalized_alias,
                )
            )
        self.session.add(
            AuditLog(
                actor_telegram_id=admin_telegram_id,
                action="title.created",
                entity_type="title",
                entity_id=str(title.id),
                payload={"slug": slug, "english_title": english_title},
            )
        )
        await self.session.commit()
        return title

    async def get_title(self, title_id: UUID, *, published_only: bool = False) -> Title | None:
        statement = select(Title).where(Title.id == title_id)
        if published_only:
            statement = statement.where(Title.is_published.is_(True))
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_title_by_slug(self, slug: str) -> Title | None:
        return (
            await self.session.execute(select(Title).where(Title.slug == slug))
        ).scalar_one_or_none()

    async def list_titles(self, *, page: int, page_size: int) -> list[Title]:
        return list(
            (
                await self.session.execute(
                    select(Title)
                    .where(Title.is_published.is_(True))
                    .order_by(Title.published_at.desc(), Title.english_title.asc())
                    .offset(max(page, 0) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )

    async def count_titles(self) -> int:
        return int(
            (
                await self.session.execute(
                    select(func.count(Title.id)).where(Title.is_published.is_(True))
                )
            ).scalar_one()
        )

    async def search_titles(self, query: str, *, limit: int = 15) -> list[Title]:
        normalized = normalize_title(query)
        if not normalized:
            return []
        pattern = f"%{normalized}%"
        statement = (
            select(Title)
            .join(TitleAlias, TitleAlias.title_id == Title.id)
            .where(
                Title.is_published.is_(True),
                or_(
                    func.lower(Title.english_title).contains(query.casefold()),
                    func.lower(Title.original_title).contains(query.casefold()),
                    TitleAlias.normalized_alias.like(pattern),
                ),
            )
            .distinct()
            .order_by(Title.english_title.asc())
            .limit(limit)
        )
        return list((await self.session.execute(statement)).scalars())

    async def create_release(
        self,
        *,
        title: Title,
        chapter_start: int,
        chapter_end: int,
        boosty_url: str | None,
        admin_telegram_id: int,
        display_name: str | None = None,
    ) -> Release:
        if chapter_start < 0 or chapter_end < chapter_start:
            raise ValueError("Invalid chapter range")
        overlap = (
            await self.session.execute(
                select(Release.id)
                .where(
                    Release.title_id == title.id,
                    Release.chapter_start <= chapter_end,
                    Release.chapter_end >= chapter_start,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if overlap is not None:
            raise ValueError("The chapter range overlaps an existing release")
        release = Release(
            title_id=title.id,
            chapter_start=chapter_start,
            chapter_end=chapter_end,
            display_name=display_name,
            boosty_url=boosty_url,
            created_by_admin_id=admin_telegram_id,
        )
        self.session.add(release)
        await self.session.flush()
        self.session.add(
            AuditLog(
                actor_telegram_id=admin_telegram_id,
                action="release.created",
                entity_type="release",
                entity_id=str(release.id),
                payload={
                    "title_id": str(title.id),
                    "chapter_start": chapter_start,
                    "chapter_end": chapter_end,
                },
            )
        )
        await self.session.commit()
        return release

    async def get_release(
        self, release_id: UUID, *, published_only: bool = False
    ) -> Release | None:
        statement = select(Release).where(Release.id == release_id)
        if published_only:
            statement = statement.where(Release.is_published.is_(True))
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def list_releases(self, title_id: UUID, *, published_only: bool = True) -> list[Release]:
        statement = select(Release).where(Release.title_id == title_id)
        if published_only:
            statement = statement.where(Release.is_published.is_(True))
        statement = statement.order_by(Release.chapter_start.asc(), Release.chapter_end.asc())
        return list((await self.session.execute(statement)).scalars())

    async def latest_releases(self, *, page: int, page_size: int) -> list[Release]:
        return list(
            (
                await self.session.execute(
                    select(Release)
                    .where(Release.is_published.is_(True))
                    .order_by(Release.published_at.desc())
                    .offset(max(page, 0) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )

    async def title_for_release(self, release: Release) -> Title:
        title = await self.session.get(Title, release.title_id)
        if title is None:
            raise RuntimeError("Release title is missing")
        return title

    async def set_title_cover(
        self,
        *,
        title: Title,
        object_key: str,
        content_type: str,
        admin_telegram_id: int,
    ) -> None:
        title.cover_object_key = object_key
        title.cover_content_type = content_type
        self.session.add(
            AuditLog(
                actor_telegram_id=admin_telegram_id,
                action="title.cover_changed",
                entity_type="title",
                entity_id=str(title.id),
                payload={"object_key": object_key, "content_type": content_type},
            )
        )
        await self.session.commit()
