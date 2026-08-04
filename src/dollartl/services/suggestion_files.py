from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from dollartl.services.suggestion_helpers import SUPPORTED_COVER_EXTENSIONS, SUPPORTED_RAW_EXTENSIONS


@dataclass(frozen=True, slots=True)
class InspectionResult:
    status: str
    message: str
    details: dict[str, object]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect_upload(
    *, filename: str, data: bytes, file_kind: str, max_bytes: int, archive_max_entries: int, archive_max_unpacked_bytes: int
) -> InspectionResult:
    if not data:
        raise ValueError("The uploaded file is empty.")
    if len(data) > max_bytes:
        raise ValueError("The uploaded file exceeds the 20 MB limit.")
    suffix = Path(filename).suffix.casefold()
    allowed = SUPPORTED_RAW_EXTENSIONS if file_kind == "raw" else SUPPORTED_COVER_EXTENSIONS
    if suffix not in allowed:
        raise ValueError(f"Unsupported {file_kind} file type.")

    details: dict[str, object] = {"extension": suffix, "size_bytes": len(data)}
    if suffix == ".pdf" and not data.startswith(b"%PDF-"):
        raise ValueError("The file extension is PDF, but the file signature is invalid.")
    if suffix in {".jpg", ".jpeg"} and not data.startswith(b"\xff\xd8\xff"):
        raise ValueError("The JPEG signature is invalid.")
    if suffix == ".png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("The PNG signature is invalid.")
    if suffix == ".webp" and not (data.startswith(b"RIFF") and data[8:12] == b"WEBP"):
        raise ValueError("The WebP signature is invalid.")
    if suffix in {".zip", ".epub", ".docx"}:
        details.update(_inspect_zip(data, archive_max_entries, archive_max_unpacked_bytes))
    return InspectionResult(status="valid", message="File structure passed validation.", details=details)


def _inspect_zip(data: bytes, max_entries: int, max_unpacked_bytes: int) -> dict[str, object]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("The archive structure is invalid.") from exc
    infos = archive.infolist()
    if len(infos) > max_entries:
        raise ValueError("The archive contains too many files.")
    total = 0
    encrypted = 0
    for info in infos:
        path = PurePosixPath(info.filename.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("The archive contains an unsafe path.")
        total += int(info.file_size)
        if info.flag_bits & 0x1:
            encrypted += 1
        if info.compress_size and info.file_size / max(info.compress_size, 1) > 250:
            raise ValueError("The archive contains a suspicious compression ratio.")
    if total > max_unpacked_bytes:
        raise ValueError("The unpacked archive would be too large.")
    if encrypted:
        raise ValueError("Password-protected archives are not accepted.")
    return {"archive_entries": len(infos), "archive_unpacked_bytes": total}


def detect_chapter_numbers(filename: str, data: bytes) -> list[int]:
    import re

    values: set[int] = set()
    for match in re.finditer(r"(?i)(?:chapter|chap|ch|глава|화|章)[\s._-]*(\d{1,7})", filename):
        values.add(int(match.group(1)))
    sample = data[:2_000_000]
    try:
        text = sample.decode("utf-8", errors="ignore")
    except Exception:
        text = ""
    for match in re.finditer(r"(?i)(?:chapter|chap|ch|глава|화|章)[\s._-]*(\d{1,7})", text):
        values.add(int(match.group(1)))
        if len(values) >= 5000:
            break
    return sorted(values)


def run_antivirus_hook(data: bytes, command: str) -> str:
    import shlex
    import subprocess
    import tempfile

    if not command.strip():
        return "not_configured"
    with tempfile.NamedTemporaryFile(delete=True) as handle:
        handle.write(data)
        handle.flush()
        parts = shlex.split(command)
        if any("{file}" in part for part in parts):
            parts = [part.replace("{file}", handle.name) for part in parts]
        else:
            parts.append(handle.name)
        try:
            result = subprocess.run(parts, capture_output=True, text=True, timeout=60, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("The antivirus hook could not inspect the upload.") from exc
        if result.returncode == 0:
            return "clean"
        if result.returncode == 1:
            raise ValueError("The uploaded file was rejected by the antivirus scanner.")
        raise ValueError("The antivirus scanner returned an unexpected error.")
