from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from dollartl.db.models import AuditLog, DeepLink, OutboxEvent, Release, Title
from dollartl.services.catalog_types import (
    ALLOWED_DEEP_TOKEN,
    CatalogSessionMixin,
    DeepLinkTarget,
    generate_deep_link_token,
)


class CatalogPublicationMixin(CatalogSessionMixin):
    async def ensure_deep_link(
        self,
        *,
        target_type: str,
        title_id: UUID | None = None,
        release_id: UUID | None = None,
    ) -> DeepLink:
        if target_type not in {"title", "release"}:
            raise ValueError("Invalid deep-link target")
        conditions = [DeepLink.target_type == target_type, DeepLink.is_active.is_(True)]
        if target_type == "title":
            if title_id is None:
                raise ValueError("title_id is required")
            conditions.append(DeepLink.title_id == title_id)
        else:
            if release_id is None:
                raise ValueError("release_id is required")
            conditions.append(DeepLink.release_id == release_id)
        existing = (
            await self.session.execute(select(DeepLink).where(*conditions).limit(1))
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        for _ in range(10):
            token = generate_deep_link_token()
            if (
                await self.session.execute(select(DeepLink.id).where(DeepLink.token == token))
            ).scalar_one_or_none() is None:
                link = DeepLink(
                    token=token,
                    target_type=target_type,
                    title_id=title_id,
                    release_id=release_id,
                )
                self.session.add(link)
                await self.session.flush()
                return link
        raise RuntimeError("Could not allocate a unique deep-link token")

    async def resolve_deep_link(self, token: str) -> DeepLinkTarget | None:
        if not ALLOWED_DEEP_TOKEN.fullmatch(token):
            return None
        link = (
            await self.session.execute(
                select(DeepLink).where(
                    DeepLink.token == token, DeepLink.is_active.is_(True)
                )
            )
        ).scalar_one_or_none()
        if link is None:
            return None
        link.uses += 1
        await self.session.commit()
        return DeepLinkTarget(
            target_type=link.target_type,
            title_id=link.title_id,
            release_id=link.release_id,
        )

    async def publish_title(self, *, title: Title, admin_telegram_id: int) -> DeepLink:
        if title.is_published:
            link = await self.ensure_deep_link(target_type="title", title_id=title.id)
            await self.session.commit()
            return link
        now = datetime.now(timezone.utc)
        title.is_published = True
        title.published_at = title.published_at or now
        link = await self.ensure_deep_link(target_type="title", title_id=title.id)
        self.session.add(
            OutboxEvent(
                topic="title.published",
                aggregate_type="title",
                aggregate_id=str(title.id),
                payload={"deep_link_token": link.token},
            )
        )
        self.session.add(
            AuditLog(
                actor_telegram_id=admin_telegram_id,
                action="title.published",
                entity_type="title",
                entity_id=str(title.id),
                payload={"deep_link_token": link.token},
            )
        )
        await self.session.commit()
        return link

    async def publish_release(self, *, release: Release, admin_telegram_id: int) -> DeepLink:
        if release.is_published:
            link = await self.ensure_deep_link(target_type="release", release_id=release.id)
            await self.session.commit()
            return link
        if release.validation_status not in {"valid", "overridden"}:
            raise ValueError(
                f"Release validation is {release.validation_status}: "
                f"{release.validation_message or 'no details'}"
            )
        files = await self.get_current_file_versions(release.id)
        if {item.release_file.file_kind for item in files} != {"pdf", "epub"}:
            raise ValueError("Both PDF and EPUB are required")
        title = await self.title_for_release(release)
        if not title.is_published:
            raise ValueError("Publish the title before publishing a release")

        now = datetime.now(timezone.utc)
        release.is_published = True
        release.published_at = release.published_at or now
        title.latest_chapter = max(title.latest_chapter, release.chapter_end)
        link = await self.ensure_deep_link(target_type="release", release_id=release.id)
        self.session.add(
            OutboxEvent(
                topic="release.published",
                aggregate_type="release",
                aggregate_id=str(release.id),
                payload={"deep_link_token": link.token, "title_id": str(title.id)},
            )
        )
        self.session.add(
            AuditLog(
                actor_telegram_id=admin_telegram_id,
                action="release.published",
                entity_type="release",
                entity_id=str(release.id),
                payload={"deep_link_token": link.token, "title_id": str(title.id)},
            )
        )
        await self.session.commit()
        return link
