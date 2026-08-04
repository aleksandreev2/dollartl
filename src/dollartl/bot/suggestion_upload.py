from __future__ import annotations

import asyncio
import io
from uuid import UUID, uuid4

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from dollartl.config import Settings
from dollartl.db.session import SessionFactory
from dollartl.services.suggestion_files import (
    detect_chapter_numbers,
    inspect_upload,
    run_antivirus_hook,
    sha256_bytes,
)
from dollartl.services.suggestion_helpers import safe_filename
from dollartl.services.suggestions import SuggestionService
from dollartl.storage import S3Storage


def _uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except (TypeError, ValueError):
        return None


async def upload_suggestion_file(
    *, message: Message, bot: Bot, state: FSMContext, settings: Settings, file_kind: str
) -> None:
    state_data = await state.get_data()
    suggestion_id = _uuid(str(state_data.get("suggestion_id", "")))
    if suggestion_id is None:
        raise ValueError("Suggestion draft could not be found.")

    if file_kind == "raw":
        if message.document is None:
            raise ValueError(
                "Upload an EPUB, TXT, ZIP, DOCX or PDF document, or use Skip Raw File."
            )
        downloadable = message.document
        filename = safe_filename(message.document.file_name or "raw-file.bin")
        content_type = message.document.mime_type or "application/octet-stream"
        size = message.document.file_size or 0
    else:
        if message.photo:
            downloadable = message.photo[-1]
            filename = "official-cover.jpg"
            content_type = "image/jpeg"
            size = downloadable.file_size or 0
        elif message.document is not None:
            downloadable = message.document
            filename = safe_filename(message.document.file_name or "official-cover.bin")
            content_type = message.document.mime_type or "application/octet-stream"
            size = message.document.file_size or 0
        else:
            raise ValueError("Upload an official JPG, PNG or WebP cover, or use Skip Cover.")

    if size > settings.user_upload_max_bytes:
        raise ValueError("The uploaded file exceeds the 20 MB limit.")
    buffer = io.BytesIO()
    await bot.download(downloadable, destination=buffer)
    payload = buffer.getvalue()
    inspection = inspect_upload(
        filename=filename,
        data=payload,
        file_kind=file_kind,
        max_bytes=settings.user_upload_max_bytes,
        archive_max_entries=settings.suggestion_archive_max_entries,
        archive_max_unpacked_bytes=settings.suggestion_archive_max_unpacked_bytes,
    )
    details = dict(inspection.details)
    chapters = detect_chapter_numbers(filename, payload)
    if chapters:
        details.update(
            detected_chapter_min=min(chapters),
            detected_chapter_max=max(chapters),
            detected_chapter_count=len(chapters),
        )
    details["antivirus"] = await asyncio.to_thread(
        run_antivirus_hook,
        payload,
        settings.suggestion_antivirus_command,
    )
    checksum = sha256_bytes(payload)
    key = f"suggestions/{suggestion_id}/{file_kind}/{uuid4()}-{filename}"
    buffer.seek(0)
    await asyncio.to_thread(
        S3Storage(settings).upload_fileobj,
        buffer,
        key,
        content_type,
    )
    async with SessionFactory() as session:
        await SuggestionService(session, settings).attach_file(
            suggestion_id=suggestion_id,
            file_kind=file_kind,
            object_key=key,
            original_filename=filename,
            content_type=content_type,
            size_bytes=len(payload),
            sha256=checksum,
            telegram_file_id=downloadable.file_id,
            telegram_file_unique_id=downloadable.file_unique_id,
            validation_status=inspection.status,
            validation_message=inspection.message,
            inspection=details,
        )
