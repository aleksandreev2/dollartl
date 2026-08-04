from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import PurePosixPath
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SUPPORTED_RAW_EXTENSIONS = {".epub", ".txt", ".zip", ".docx", ".pdf"}
SUPPORTED_COVER_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().strip()
    return " ".join(value.split())


def normalize_source_url(value: str) -> str:
    raw = value.strip()
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Every source must be a valid http or https URL.")
    host = parsed.netloc.casefold()
    path = parsed.path.rstrip("/") or "/"
    filtered = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if not k.casefold().startswith("utm_")]
    return urlunsplit((parsed.scheme.casefold(), host, path, urlencode(filtered), ""))


def parse_source_lines(text: str, maximum: int) -> list[tuple[str, str]]:
    values = [line.strip() for line in re.split(r"[\r\n]+", text) if line.strip()]
    if not values:
        raise ValueError("Send at least one source URL.")
    if len(values) > maximum:
        raise ValueError(f"You can add up to {maximum} source URLs.")
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_source_url(value)
        if normalized not in seen:
            result.append((value, normalized))
            seen.add(normalized)
    return result


def quota_month(moment: datetime | None = None) -> date:
    current = moment or datetime.now(timezone.utc)
    return date(current.year, current.month, 1)


def quota_limit(*, vip: bool, standard_limit: int, vip_limit: int, administrator: bool = False) -> int:
    if administrator:
        return 1_000_000
    return vip_limit if vip else standard_limit


def requested_scope(*, chapter_count: int, vip: bool, standard_cap: int, administrator: bool = False) -> tuple[int, int]:
    if chapter_count < 1:
        raise ValueError("Chapter count must be positive.")
    end = chapter_count if vip or administrator else min(chapter_count, standard_cap)
    return 1, end


def safe_filename(filename: str) -> str:
    name = PurePosixPath(filename.replace("\\", "/")).name
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return cleaned[:180] or "upload.bin"


def detect_title_language(value: str) -> str | None:
    counts = {
        "Korean": sum("\uac00" <= ch <= "\ud7a3" for ch in value),
        "Japanese": sum(("\u3040" <= ch <= "\u30ff") for ch in value),
        "Chinese": sum(("\u4e00" <= ch <= "\u9fff") for ch in value),
    }
    language, amount = max(counts.items(), key=lambda item: item[1])
    if amount == 0:
        return None
    if language == "Chinese" and counts["Japanese"]:
        return "Japanese"
    return language
