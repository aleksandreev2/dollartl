from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any
from uuid import UUID

from aiogram import Bot
from aiogram.types import FSInputFile
from sqlalchemy import select, text

from dollartl import __version__
from dollartl.config import Settings
from dollartl.db.resilience_models import BackupRun
from dollartl.db.session import SessionFactory, engine
from dollartl.resilience.crypto import EncryptionResult, decrypt_file, encrypt_file, hash_file
from dollartl.resilience.health import migration_status
from dollartl.storage import S3Storage

logger = logging.getLogger(__name__)
BACKUP_LOCK_ID = 481_516_234
COMMAND_TIMEOUT_SECONDS = 60 * 30
FAILURE_RETRY_HOURS = 6


@dataclass(frozen=True, slots=True)
class ReplicationResult:
    source_count: int
    copied_count: int
    copied_bytes: int
    verified: bool
    objects: list[dict[str, Any]]


async def _run_command(*arguments: str) -> str:
    process = await asyncio.create_subprocess_exec(
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=COMMAND_TIMEOUT_SECONDS
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        raise RuntimeError(f"Command timed out: {arguments[0]}")
    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"{arguments[0]} failed: {message[-4000:]}")
    return stdout.decode("utf-8", errors="replace")


async def _dump_database(settings: Settings, destination: Path) -> None:
    await _run_command(
        "pg_dump",
        "--format=custom",
        "--compress=6",
        "--no-owner",
        "--no-acl",
        f"--dbname={settings.postgres_dsn.get_secret_value()}",
        f"--file={destination}",
    )


async def _verify_archive(
    settings: Settings,
    encrypted_path: Path,
    decrypted_path: Path,
) -> dict[str, Any]:
    result = decrypt_file(
        encrypted_path,
        decrypted_path,
        settings.backup_encryption_key.get_secret_value(),
    )
    listing = await _run_command("pg_restore", "--list", str(decrypted_path))
    entries = sum(1 for line in listing.splitlines() if line and not line.startswith(";"))
    if entries < 1:
        raise RuntimeError("pg_restore did not find any archive entries")
    restore_verified = False
    verify_dsn = settings.backup_verify_dsn.get_secret_value()
    if verify_dsn:
        await _run_command(
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-acl",
            "--exit-on-error",
            f"--dbname={verify_dsn}",
            str(decrypted_path),
        )
        await _run_command(
            "psql",
            verify_dsn,
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "SELECT version_num FROM alembic_version;",
        )
        restore_verified = True
    return {
        "archive_entries": entries,
        "decrypt_chunks": result.chunks,
        "restore_verified": restore_verified,
        "verification_mode": "dedicated_database" if verify_dsn else "decrypt_and_pg_restore_list",
    }


def _replicate_storage(settings: Settings) -> ReplicationResult:
    if not settings.backup_replication_enabled:
        return ReplicationResult(0, 0, 0, True, [])
    source = S3Storage(settings)
    target = S3Storage.backup(settings)
    source.ensure_bucket_access()
    target.ensure_bucket_access()
    same_storage = (
        source.bucket == target.bucket
        and source.client.meta.endpoint_url == target.client.meta.endpoint_url
    )
    objects: list[dict[str, Any]] = []
    copied_count = 0
    copied_bytes = 0
    verified = True
    for item in source.iter_objects():
        key = str(item["Key"])
        if same_storage and key.startswith(("database/", "storage-mirror/")):
            continue
        size = int(item.get("Size", 0))
        etag = str(item.get("ETag", "")).strip('"')
        destination_key = f"storage-mirror/{key}"
        target_head = target.head(destination_key)
        metadata = (target_head or {}).get("Metadata", {})
        already_current = bool(
            target_head
            and int(target_head.get("ContentLength", -1)) == size
            and metadata.get("source-etag") == etag
            and metadata.get("source-size") == str(size)
        )
        copied = False
        if not already_current:
            response = source.client.get_object(Bucket=source.bucket, Key=key)
            content_type = (
                response.get("ContentType")
                or mimetypes.guess_type(key)[0]
                or "application/octet-stream"
            )
            body = response["Body"]
            try:
                target.client.upload_fileobj(
                    body,
                    target.bucket,
                    destination_key,
                    ExtraArgs={
                        "ContentType": content_type,
                        "Metadata": {"source-etag": etag, "source-size": str(size)},
                    },
                )
            finally:
                body.close()
            copied = True
            copied_count += 1
            copied_bytes += size
        final_head = target.head(destination_key)
        object_verified = bool(
            final_head and int(final_head.get("ContentLength", -1)) == size
        )
        verified = verified and object_verified
        objects.append(
            {
                "source_key": key,
                "backup_key": destination_key,
                "size": size,
                "source_etag": etag,
                "copied": copied,
                "verified": object_verified,
            }
        )
    return ReplicationResult(
        source_count=len(objects),
        copied_count=copied_count,
        copied_bytes=copied_bytes,
        verified=verified,
        objects=objects,
    )


async def request_backup(
    *, admin_telegram_id: int, trigger_type: str = "manual"
) -> BackupRun:
    async with SessionFactory() as session:
        existing = (
            await session.execute(
                select(BackupRun)
                .where(BackupRun.status.in_(["queued", "running"]))
                .order_by(BackupRun.created_at.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        run = BackupRun(
            status="queued",
            trigger_type=trigger_type,
            requested_by_admin_id=admin_telegram_id,
        )
        session.add(run)
        await session.commit()
        return run


async def _claim_backup(settings: Settings) -> BackupRun | None:
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(hours=2)
    async with SessionFactory() as session:
        stale = list(
            (
                await session.execute(
                    select(BackupRun).where(
                        BackupRun.status == "running",
                        BackupRun.started_at < stale_before,
                    )
                )
            ).scalars()
        )
        for item in stale:
            item.status = "failed"
            item.completed_at = now
            item.error = "Backup worker lease expired while the run was active"

        queued = (
            await session.execute(
                select(BackupRun)
                .where(BackupRun.status == "queued")
                .order_by(BackupRun.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(1)
            )
        ).scalar_one_or_none()
        if queued is None and settings.backup_enabled:
            last_success = (
                await session.execute(
                    select(BackupRun.completed_at)
                    .where(BackupRun.status == "succeeded")
                    .order_by(BackupRun.completed_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            last_failure = (
                await session.execute(
                    select(BackupRun.completed_at)
                    .where(BackupRun.status == "failed")
                    .order_by(BackupRun.completed_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            due_before = now - timedelta(hours=settings.backup_interval_hours)
            retry_before = now - timedelta(hours=FAILURE_RETRY_HOURS)
            success_due = last_success is None or last_success <= due_before
            failure_cooled_down = last_failure is None or last_failure <= retry_before
            if success_due and failure_cooled_down:
                queued = BackupRun(status="queued", trigger_type="scheduled")
                session.add(queued)
                await session.flush()
        if queued is None:
            await session.commit()
            return None
        queued.status = "running"
        queued.started_at = now
        queued.error = None
        await session.commit()
        return queued


async def _mark_failed(run_id: UUID, error: BaseException) -> None:
    async with SessionFactory() as session:
        run = await session.get(BackupRun, run_id)
        if run is None:
            return
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        run.error = f"{type(error).__name__}: {error}"[:8000]
        await session.commit()


async def _deliver_backup(
    bot: Bot,
    settings: Settings,
    run: BackupRun,
    encrypted_path: Path,
) -> tuple[str, int | None]:
    caption = (
        "🗄 <b>DOLLAR TL BACKUP</b>\n\n"
        f"Run: <code>{run.id}</code>\n"
        "Database archive: verified\n"
        f"Restore test: {'verified' if run.restore_verified else 'archive-level only'}\n"
        f"Storage mirror: {'verified' if run.storage_replication_verified else 'not verified'}\n"
        f"Encrypted size: {run.encrypted_size_bytes or 0} bytes"
    )
    if encrypted_path.stat().st_size <= settings.backup_telegram_max_bytes:
        sent = await bot.send_document(
            settings.admin_telegram_id,
            FSInputFile(encrypted_path, filename=encrypted_path.name),
            caption=caption,
            protect_content=True,
        )
        return "sent", sent.message_id
    if not run.database_object_key:
        raise RuntimeError("Backup object key is missing")
    url = await asyncio.to_thread(
        S3Storage.backup(settings).presigned_get_url,
        run.database_object_key,
        expires_seconds=settings.backup_download_url_seconds,
        filename=encrypted_path.name,
    )
    sent = await bot.send_message(
        settings.admin_telegram_id,
        caption
        + "\n\nThe encrypted archive is larger than the Telegram upload limit. "
        + f'<a href="{escape(url, quote=True)}">Download backup</a> '
        + f"(link expires in {settings.backup_download_url_seconds // 3600} hours).",
        protect_content=True,
        disable_web_page_preview=True,
    )
    return "linked", sent.message_id


async def _apply_retention(settings: Settings) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.backup_retention_days)
    async with SessionFactory() as session:
        successful = list(
            (
                await session.execute(
                    select(BackupRun)
                    .where(BackupRun.status == "succeeded")
                    .order_by(BackupRun.completed_at.desc())
                )
            ).scalars()
        )
        candidates = [
            item
            for index, item in enumerate(successful)
            if index >= settings.backup_retention_count
            or (item.completed_at is not None and item.completed_at < cutoff)
        ]
        if not candidates:
            return 0
        storage = S3Storage.backup(settings)
        removed = 0
        for item in candidates:
            keys = [
                key
                for key in (
                    item.database_object_key,
                    item.manifest_object_key,
                    item.storage_manifest_object_key,
                )
                if key
            ]
            await asyncio.to_thread(storage.delete_many, keys)
            item.database_object_key = None
            item.manifest_object_key = None
            item.storage_manifest_object_key = None
            details = dict(item.verification_details or {})
            details["retention_pruned_at"] = datetime.now(timezone.utc).isoformat()
            item.verification_details = details
            removed += 1
        await session.commit()
        return removed


async def _execute_backup(bot: Bot, settings: Settings, run: BackupRun) -> None:
    secret = settings.backup_encryption_key.get_secret_value()
    if not secret:
        raise RuntimeError("BACKUP_ENCRYPTION_KEY is required when backups are enabled")
    workdir = Path(settings.backup_temp_dir) / f"dollartl-{run.id}"
    workdir.mkdir(parents=True, exist_ok=False)
    dump_path = workdir / "database.dump"
    encrypted_path = workdir / f"dollartl-{run.id}.dtlbak"
    decrypted_path = workdir / "database-verified.dump"
    manifest_path = workdir / "manifest.json"
    storage_manifest_path = workdir / "storage-manifest.json"
    try:
        await _dump_database(settings, dump_path)
        encryption: EncryptionResult = await asyncio.to_thread(
            encrypt_file,
            dump_path,
            encrypted_path,
            secret,
        )
        verification = await _verify_archive(settings, encrypted_path, decrypted_path)
        if hash_file(decrypted_path)[1] != encryption.plaintext_sha256:
            raise RuntimeError("Decrypted database checksum does not match the source dump")
        replication = await asyncio.to_thread(_replicate_storage, settings)
        migration = await migration_status()
        storage_manifest = {
            "backup_run_id": str(run.id),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_bucket": settings.s3_bucket,
            "backup_bucket": settings.s3_backup_bucket,
            **asdict(replication),
        }
        storage_manifest_path.write_text(
            json.dumps(storage_manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        prefix = f"database/{stamp}-{run.id}"
        database_key = f"{prefix}/database.dtlbak"
        storage_manifest_key = f"{prefix}/storage-manifest.json"
        manifest_key = f"{prefix}/manifest.json"
        manifest = {
            "format_version": 1,
            "application": "Dollar TL",
            "application_version": __version__,
            "backup_run_id": str(run.id),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database": {"object_key": database_key, **asdict(encryption)},
            "migrations": {
                "current": list(migration.current),
                "expected": list(migration.expected),
                "matches": migration.matches,
            },
            "verification": verification,
            "storage": {
                "manifest_object_key": storage_manifest_key,
                "source_count": replication.source_count,
                "copied_count": replication.copied_count,
                "copied_bytes": replication.copied_bytes,
                "verified": replication.verified,
            },
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        backup_storage = S3Storage.backup(settings)
        await asyncio.to_thread(backup_storage.ensure_bucket_access)
        await asyncio.to_thread(
            backup_storage.upload_path,
            encrypted_path,
            database_key,
            "application/octet-stream",
        )
        await asyncio.to_thread(
            backup_storage.upload_path,
            storage_manifest_path,
            storage_manifest_key,
            "application/json",
        )
        await asyncio.to_thread(
            backup_storage.upload_path,
            manifest_path,
            manifest_key,
            "application/json",
        )
        async with SessionFactory() as session:
            persisted = await session.get(BackupRun, run.id)
            if persisted is None:
                raise RuntimeError("Backup run disappeared")
            persisted.database_object_key = database_key
            persisted.manifest_object_key = manifest_key
            persisted.storage_manifest_object_key = storage_manifest_key
            persisted.plaintext_size_bytes = encryption.plaintext_size
            persisted.encrypted_size_bytes = encryption.encrypted_size
            persisted.plaintext_sha256 = encryption.plaintext_sha256
            persisted.encrypted_sha256 = encryption.encrypted_sha256
            persisted.database_archive_verified = True
            persisted.restore_verified = bool(verification["restore_verified"])
            persisted.storage_replication_verified = replication.verified
            persisted.verification_details = {
                **verification,
                "migrations_match": migration.matches,
            }
            persisted.source_object_count = replication.source_count
            persisted.replicated_object_count = replication.copied_count
            persisted.replicated_bytes = replication.copied_bytes
            await session.commit()
            session.expunge(persisted)
        try:
            delivery_status, message_id = await _deliver_backup(
                bot, settings, persisted, encrypted_path
            )
        except Exception as delivery_error:
            logger.exception("backup_telegram_delivery_failed")
            delivery_status, message_id = "failed", None
            verification_details = dict(persisted.verification_details or {})
            verification_details["telegram_error"] = (
                f"{type(delivery_error).__name__}: {delivery_error}"[:2000]
            )
        else:
            verification_details = dict(persisted.verification_details or {})
        async with SessionFactory() as session:
            completed = await session.get(BackupRun, run.id)
            if completed is None:
                raise RuntimeError("Backup run disappeared before completion")
            completed.status = "succeeded"
            completed.completed_at = datetime.now(timezone.utc)
            completed.telegram_delivery_status = delivery_status
            completed.telegram_message_id = message_id
            completed.verification_details = verification_details
            await session.commit()
        try:
            await _apply_retention(settings)
        except Exception as retention_error:
            logger.exception("backup_retention_failed")
            async with SessionFactory() as session:
                completed = await session.get(BackupRun, run.id)
                if completed is not None:
                    details = dict(completed.verification_details or {})
                    details["retention_error"] = (
                        f"{type(retention_error).__name__}: {retention_error}"[:2000]
                    )
                    completed.verification_details = details
                    await session.commit()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def process_next_backup(bot: Bot, settings: Settings) -> bool:
    async with engine.connect() as connection:
        acquired = bool(
            await connection.scalar(
                text("SELECT pg_try_advisory_lock(:lock_id)"),
                {"lock_id": BACKUP_LOCK_ID},
            )
        )
        if not acquired:
            return False
        try:
            run = await _claim_backup(settings)
            if run is None:
                return False
            try:
                await _execute_backup(bot, settings, run)
            except Exception as exc:
                logger.exception("backup_run_failed", extra={"backup_run_id": str(run.id)})
                await _mark_failed(run.id, exc)
                try:
                    await bot.send_message(
                        settings.admin_telegram_id,
                        "⚠️ <b>DOLLAR TL BACKUP FAILED</b>\n\n"
                        f"Run: <code>{run.id}</code>\n"
                        f"Error: <code>{type(exc).__name__}</code>\n"
                        "Open the Admin Mini App for details.",
                    )
                except Exception:
                    logger.exception("backup_failure_notification_failed")
            return True
        finally:
            await connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": BACKUP_LOCK_ID},
            )
