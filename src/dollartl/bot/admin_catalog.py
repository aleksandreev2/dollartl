from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from dollartl.db.models import Title

from dollartl.config import Settings
from dollartl.db.session import SessionFactory
from dollartl.files.chapter_detection import detect_chapter_range
from dollartl.services.access import AccessService
from dollartl.services.catalog import CatalogService
from dollartl.storage import S3Storage


def _is_admin(message: Message, settings: Settings) -> bool:
    return message.from_user is not None and message.from_user.id == settings.admin_telegram_id


def _uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValueError("Некорректный UUID") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _deep_url(settings: Settings, token: str) -> str:
    username = settings.normalized_bot_username
    return f"https://t.me/{username}?start={token}" if username else token


def create_admin_catalog_router(settings: Settings) -> Router:
    router = Router(name="admin_catalog")

    @router.message(Command("title_create"))
    async def title_create(message: Message) -> None:
        if not _is_admin(message, settings):
            return
        raw = (message.text or "").partition(" ")[2]
        parts = [part.strip() for part in raw.split("|")]
        if len(parts) < 4:
            await message.answer(
                "Использование:\n"
                "/title_create English title | Original title | Language | ongoing|completed|hiatus | Boosty URL | Description"
            )
            return
        english, original, language, status = parts[:4]
        boosty_url = parts[4] if len(parts) > 4 and parts[4] else None
        description = parts[5] if len(parts) > 5 else ""
        try:
            async with SessionFactory() as session:
                title = await CatalogService(session).create_title(
                    english_title=english,
                    original_title=original,
                    original_language=language,
                    publication_status=status.lower(),
                    boosty_url=boosty_url,
                    description=description,
                    admin_telegram_id=settings.admin_telegram_id,
                )
        except ValueError as exc:
            await message.answer(f"Ошибка: {exc}")
            return
        await message.answer(
            f"Тайтл создан.\nSlug: <code>{title.slug}</code>\nID: <code>{title.id}</code>"
        )

    @router.message(Command("title_list"))
    async def title_list(message: Message) -> None:
        if not _is_admin(message, settings):
            return
        async with SessionFactory() as session:
            titles = await CatalogService(session).list_titles(page=0, page_size=100)
            unpublished = list(
                (
                    await session.execute(
                        select(Title)
                        .where(Title.is_published.is_(False))
                        .order_by(Title.created_at.desc())
                    )
                ).scalars()
            )
        all_titles = [*titles, *unpublished]
        if not all_titles:
            await message.answer("Тайтлов пока нет.")
            return
        lines = [
            f"• <code>{title.slug}</code> — {title.english_title} "
            f"({'published' if title.is_published else 'draft'})"
            for title in all_titles
        ]
        await message.answer("<b>Тайтлы</b>\n\n" + "\n".join(lines[:100]))

    @router.message(Command("release_create"))
    async def release_create(message: Message) -> None:
        if not _is_admin(message, settings):
            return
        parts = (message.text or "").split(maxsplit=3)
        if len(parts) < 3 or "-" not in parts[2]:
            await message.answer(
                "Использование: /release_create <title_slug> <start-end> [Boosty URL]"
            )
            return
        slug = parts[1]
        try:
            start_raw, end_raw = parts[2].split("-", maxsplit=1)
            start, end = int(start_raw), int(end_raw)
            async with SessionFactory() as session:
                service = CatalogService(session)
                title = await service.get_title_by_slug(slug)
                if title is None:
                    raise ValueError("Тайтл не найден")
                release = await service.create_release(
                    title=title,
                    chapter_start=start,
                    chapter_end=end,
                    boosty_url=parts[3].strip() if len(parts) == 4 else None,
                    admin_telegram_id=settings.admin_telegram_id,
                )
        except ValueError as exc:
            await message.answer(f"Ошибка: {exc}")
            return
        await message.answer(
            f"Пакет создан: {release.chapter_label}\nID: <code>{release.id}</code>\n"
            f"Теперь прикрепите оба файла через /attach_file."
        )

    @router.message(Command("attach_file"), F.document)
    async def attach_file(message: Message, bot: Bot) -> None:
        if not _is_admin(message, settings) or message.document is None:
            return
        parts = (message.caption or message.text or "").split()
        if len(parts) < 3:
            await message.answer(
                "Добавьте подпись к документу: /attach_file <release_uuid> <pdf|epub>"
            )
            return
        try:
            release_id = _uuid(parts[1])
            file_kind = parts[2].lower()
            if file_kind not in {"pdf", "epub"}:
                raise ValueError("Формат должен быть pdf или epub")
            async with SessionFactory() as session:
                release = await CatalogService(session).get_release(release_id)
            if release is None:
                raise ValueError("Пакет не найден")
        except ValueError as exc:
            await message.answer(f"Ошибка: {exc}")
            return

        original_filename = message.document.file_name or f"release-{release_id}.{file_kind}"
        suffix = f".{file_kind}"
        temporary = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        temporary.close()
        path = Path(temporary.name)
        try:
            await bot.download(message.document, destination=path)
            detection = await asyncio.to_thread(
                detect_chapter_range, path, file_kind, original_filename
            )
            digest = await asyncio.to_thread(_sha256, path)
            content_type = (
                "application/pdf"
                if file_kind == "pdf"
                else "application/epub+zip"
            )
            object_key = (
                f"titles/releases/{release_id}/{file_kind}/"
                f"{uuid4().hex}-{Path(original_filename).name}"
            )
            storage = S3Storage(settings)
            with path.open("rb") as stream:
                stored = await asyncio.to_thread(
                    storage.upload_fileobj, stream, object_key, content_type
                )
            async with SessionFactory() as session:
                service = CatalogService(session)
                persisted_release = await service.get_release(release_id)
                if persisted_release is None:
                    raise ValueError("Пакет исчез во время загрузки")
                version = await service.attach_release_file(
                    release=persisted_release,
                    file_kind=file_kind,
                    object_key=stored.key,
                    original_filename=original_filename,
                    content_type=content_type,
                    size_bytes=stored.size,
                    sha256=digest,
                    telegram_file_id=message.document.file_id,
                    telegram_file_unique_id=message.document.file_unique_id,
                    detection=detection.as_dict(),
                    admin_telegram_id=settings.admin_telegram_id,
                )
                status = persisted_release.validation_status
                validation_message = persisted_release.validation_message
        except Exception as exc:
            await message.answer(f"Загрузка не выполнена: {type(exc).__name__}: {exc}")
            return
        finally:
            path.unlink(missing_ok=True)

        await message.answer(
            f"{file_kind.upper()} сохранён как версия {version.version}.\n"
            f"Определено: {detection.chapter_start}–{detection.chapter_end} "
            f"({detection.source}, {detection.confidence})\n"
            f"Статус пакета: <b>{status}</b>\n{validation_message or ''}"
        )

    @router.message(Command("title_cover"))
    async def title_cover(message: Message, bot: Bot) -> None:
        if not _is_admin(message, settings):
            return
        parts = (message.caption or message.text or "").split()
        if len(parts) < 2 or (not message.photo and message.document is None):
            await message.answer(
                "Отправьте изображение с подписью /title_cover <title_slug>"
            )
            return
        slug = parts[1]
        file_id: str
        unique_id: str
        filename: str
        content_type: str
        if message.photo:
            item = message.photo[-1]
            file_id = item.file_id
            unique_id = item.file_unique_id
            filename = f"cover-{unique_id}.jpg"
            content_type = "image/jpeg"
        else:
            assert message.document is not None
            file_id = message.document.file_id
            unique_id = message.document.file_unique_id
            filename = message.document.file_name or f"cover-{unique_id}.jpg"
            content_type = message.document.mime_type or mimetypes.guess_type(filename)[0] or "image/jpeg"
        if not content_type.startswith("image/"):
            await message.answer("Обложка должна быть изображением.")
            return
        temporary = tempfile.NamedTemporaryFile(suffix=Path(filename).suffix or ".jpg", delete=False)
        temporary.close()
        path = Path(temporary.name)
        try:
            await bot.download(file_id, destination=path)
            object_key = f"titles/covers/{uuid4().hex}-{Path(filename).name}"
            storage = S3Storage(settings)
            with path.open("rb") as stream:
                stored = await asyncio.to_thread(
                    storage.upload_fileobj, stream, object_key, content_type
                )
            async with SessionFactory() as session:
                service = CatalogService(session)
                title = await service.get_title_by_slug(slug)
                if title is None:
                    raise ValueError("Тайтл не найден")
                await service.set_title_cover(
                    title=title,
                    object_key=stored.key,
                    content_type=content_type,
                    admin_telegram_id=settings.admin_telegram_id,
                )
        except Exception as exc:
            await message.answer(f"Не удалось сохранить обложку: {exc}")
            return
        finally:
            path.unlink(missing_ok=True)
        await message.answer("Обложка сохранена.")

    @router.message(Command("release_override"))
    async def release_override(message: Message) -> None:
        if not _is_admin(message, settings):
            return
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 3:
            await message.answer("Использование: /release_override <uuid> <причина>")
            return
        try:
            release_id = _uuid(parts[1])
            async with SessionFactory() as session:
                service = CatalogService(session)
                release = await service.get_release(release_id)
                if release is None:
                    raise ValueError("Пакет не найден")
                await service.override_release_validation(
                    release=release,
                    admin_telegram_id=settings.admin_telegram_id,
                    reason=parts[2],
                )
        except ValueError as exc:
            await message.answer(f"Ошибка: {exc}")
            return
        await message.answer("Проверка пакета подтверждена вручную.")

    @router.message(Command("publish_title"))
    async def publish_title(message: Message) -> None:
        if not _is_admin(message, settings):
            return
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Использование: /publish_title <slug>")
            return
        async with SessionFactory() as session:
            service = CatalogService(session)
            title = await service.get_title_by_slug(parts[1].strip())
            if title is None:
                await message.answer("Тайтл не найден.")
                return
            link = await service.publish_title(
                title=title, admin_telegram_id=settings.admin_telegram_id
            )
        await message.answer(f"Тайтл опубликован.\nDeep link: {_deep_url(settings, link.token)}")

    @router.message(Command("publish_release"))
    async def publish_release(message: Message) -> None:
        if not _is_admin(message, settings):
            return
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Использование: /publish_release <release_uuid>")
            return
        try:
            release_id = _uuid(parts[1].strip())
            async with SessionFactory() as session:
                service = CatalogService(session)
                release = await service.get_release(release_id)
                if release is None:
                    raise ValueError("Пакет не найден")
                link = await service.publish_release(
                    release=release, admin_telegram_id=settings.admin_telegram_id
                )
        except ValueError as exc:
            await message.answer(f"Публикация заблокирована: {exc}")
            return
        await message.answer(f"Пакет опубликован.\nDeep link: {_deep_url(settings, link.token)}")

    @router.message(Command("download_access"))
    async def download_access(message: Message) -> None:
        if not _is_admin(message, settings):
            return
        parts = (message.text or "").split()
        if len(parts) != 3 or parts[2].lower() not in {"on", "off"}:
            await message.answer("Использование: /download_access <telegram_id> on|off")
            return
        try:
            target_id = int(parts[1])
        except ValueError:
            await message.answer("Telegram ID должен быть числом.")
            return
        async with SessionFactory() as session:
            access = AccessService(session)
            target = await access.get_user_by_telegram_id(target_id)
            if target is None:
                await message.answer("Пользователь ещё не зарегистрирован в боте.")
                return
            enabled = parts[2].lower() == "on"
            await access.set_manual_download_access(
                target=target,
                enabled=enabled,
                admin_telegram_id=settings.admin_telegram_id,
            )
        await message.answer(f"Прямое скачивание: {'включено' if enabled else 'выключено'}.")

    return router
