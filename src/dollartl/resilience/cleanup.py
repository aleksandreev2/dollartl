from __future__ import annotations

import asyncio
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dollartl.config import Settings


def _cleanup(settings: Settings) -> dict[str, int]:
    root = Path(settings.backup_temp_dir)
    root.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.backup_temp_retention_hours)
    removed_files = 0
    removed_directories = 0
    for item in root.iterdir():
        try:
            modified = datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc)
        except FileNotFoundError:
            continue
        if modified >= cutoff:
            continue
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
            removed_directories += 1
        else:
            item.unlink(missing_ok=True)
            removed_files += 1
    return {"files": removed_files, "directories": removed_directories}


async def cleanup_temporary_files(settings: Settings) -> dict[str, int]:
    return await asyncio.to_thread(_cleanup, settings)
