from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, select, update

from dollartl.db.catalog_revision_models import FileVersionInspection
from dollartl.db.models import AuditLog, DownloadEvent, FileVersion, Release, ReleaseFile, User
from dollartl.services.catalog_types import CatalogSessionMixin, ReleaseFileBundle


class CatalogFilesMixin(CatalogSessionMixin):
    async def attach_release_file(
        self,
        *,
        release: Release,
        file_kind: str,
        object_key: str,
        original_filename: str,
        content_type: str,
        size_bytes: int,
        sha256: str,
        telegram_file_id: str | None,
        telegram_file_unique_id: str | None,
        detection: dict[str, object],
        admin_telegram_id: int,
    ) -> FileVersion:
        if file_kind not in {"pdf", "epub"}:
            raise ValueError("file_kind must be pdf or epub")
        release_file = (
            await self.session.execute(
                select(ReleaseFile).where(
                    ReleaseFile.release_id == release.id,
                    ReleaseFile.file_kind == file_kind,
                )
            )
        ).scalar_one_or_none()
        if release_file is None:
            release_file = ReleaseFile(release_id=release.id, file_kind=file_kind)
            self.session.add(release_file)
            await self.session.flush()

        await self.session.execute(
            update(FileVersion)
            .where(FileVersion.release_file_id == release_file.id)
            .values(is_active=False)
        )
        next_version = release_file.current_version + 1
        version = FileVersion(
            release_file_id=release_file.id,
            version=next_version,
            object_key=object_key,
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=size_bytes,
            sha256=sha256,
            telegram_file_id=telegram_file_id,
            telegram_file_unique_id=telegram_file_unique_id,
            is_active=True,
            created_by_admin_id=admin_telegram_id,
        )
        release_file.current_version = next_version
        self.session.add(version)
        await self.session.flush()
        self.session.add(
            FileVersionInspection(file_version_id=version.id, inspection=detection)
        )

        report = dict(release.detection_report or {})
        report[file_kind] = detection
        release.detection_report = report
        await self._refresh_release_validation(release)
        self.session.add(
            AuditLog(
                actor_telegram_id=admin_telegram_id,
                action="release.file_attached",
                entity_type="release",
                entity_id=str(release.id),
                payload={
                    "file_kind": file_kind,
                    "version": next_version,
                    "sha256": sha256,
                    "validation_status": release.validation_status,
                },
            )
        )
        await self.session.commit()
        return version

    async def _refresh_release_validation(self, release: Release) -> None:
        report = release.detection_report or {}
        missing = [kind for kind in ("pdf", "epub") if kind not in report]
        if missing:
            release.validation_status = "pending"
            release.validation_message = f"Missing files: {', '.join(missing).upper()}"
            return
        ranges: dict[str, tuple[int | None, int | None]] = {}
        for kind in ("pdf", "epub"):
            item = report.get(kind) or {}
            start = item.get("chapter_start") if isinstance(item, dict) else None
            end = item.get("chapter_end") if isinstance(item, dict) else None
            ranges[kind] = (
                int(start) if isinstance(start, int) else None,
                int(end) if isinstance(end, int) else None,
            )
        expected = (release.chapter_start, release.chapter_end)
        if any(start is None or end is None for start, end in ranges.values()):
            release.validation_status = "warning"
            release.validation_message = "Chapter range could not be detected in every file"
        elif all(value == expected for value in ranges.values()):
            release.validation_status = "valid"
            release.validation_message = "PDF and EPUB match the declared chapter range"
        else:
            release.validation_status = "error"
            release.validation_message = (
                f"Declared {expected[0]}–{expected[1]}; "
                f"PDF {ranges['pdf'][0]}–{ranges['pdf'][1]}; "
                f"EPUB {ranges['epub'][0]}–{ranges['epub'][1]}"
            )

    async def override_release_validation(
        self, *, release: Release, admin_telegram_id: int, reason: str
    ) -> None:
        if len(reason.strip()) < 5:
            raise ValueError("Override reason is too short")
        release.validation_status = "overridden"
        release.validation_message = reason.strip()
        self.session.add(
            AuditLog(
                actor_telegram_id=admin_telegram_id,
                action="release.validation_overridden",
                entity_type="release",
                entity_id=str(release.id),
                payload={"reason": reason.strip()},
            )
        )
        await self.session.commit()

    async def get_current_file_versions(self, release_id: UUID) -> list[ReleaseFileBundle]:
        rows = (
            await self.session.execute(
                select(ReleaseFile, FileVersion)
                .join(
                    FileVersion,
                    and_(
                        FileVersion.release_file_id == ReleaseFile.id,
                        FileVersion.is_active.is_(True),
                    ),
                )
                .where(ReleaseFile.release_id == release_id)
                .order_by(ReleaseFile.file_kind.asc())
            )
        ).all()
        return [ReleaseFileBundle(release_file=row[0], version=row[1]) for row in rows]

    async def update_telegram_file_cache(
        self,
        *,
        version_id: UUID,
        telegram_file_id: str,
        telegram_file_unique_id: str | None,
    ) -> None:
        await self.session.execute(
            update(FileVersion)
            .where(FileVersion.id == version_id)
            .values(
                telegram_file_id=telegram_file_id,
                telegram_file_unique_id=telegram_file_unique_id,
            )
        )
        await self.session.commit()

    async def record_download(
        self,
        *,
        user_id: UUID,
        release_id: UUID,
        file_version_id: UUID | None,
        delivery_method: str,
        status: str,
    ) -> None:
        self.session.add(
            DownloadEvent(
                user_id=user_id,
                release_id=release_id,
                file_version_id=file_version_id,
                delivery_method=delivery_method,
                status=status,
            )
        )
        await self.session.commit()

    async def can_download_directly(self, user: User, admin_telegram_id: int) -> bool:
        from dollartl.config import get_settings
        from dollartl.services.boosty import BoostyService

        return await BoostyService(self.session, get_settings()).can_download(
            user, admin_telegram_id
        )
