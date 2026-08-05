from __future__ import annotations

import html
import re
import unicodedata
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from dollartl.files.chapter_detection import DetectionResult, detect_chapter_range

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_RANGE_RE = re.compile(
    r"(?i)(?:chapters?|chs?|глав(?:ы|а)?|том)\s*[._ -]*\d{1,6}\s*[-–—_]\s*\d{1,6}"
)
_VERSION_RE = re.compile(r"(?i)\b(?:pdf|epub|ebook|book|версия|version|v)\s*\d*\b")
_BRACKET_RE = re.compile(r"\[[^\]]{0,80}\]|\([^)]{0,80}\)")
_LANGUAGE_NAMES = {
    "ru": "Russian",
    "rus": "Russian",
    "russian": "Russian",
    "русский": "Russian",
    "en": "English",
    "eng": "English",
    "english": "English",
    "ko": "Korean",
    "kor": "Korean",
    "korean": "Korean",
    "한국어": "Korean",
    "ja": "Japanese",
    "jpn": "Japanese",
    "japanese": "Japanese",
    "日本語": "Japanese",
    "zh": "Chinese",
    "zho": "Chinese",
    "chi": "Chinese",
    "chinese": "Chinese",
    "中文": "Chinese",
}


@dataclass(frozen=True, slots=True)
class AnalysedCatalogFile:
    kind: str
    filename: str
    title: str | None
    language: str | None
    text_language: str | None
    description: str | None
    creator: str | None
    chapter_detection: DetectionResult

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["chapter_detection"] = self.chapter_detection.as_dict()
        return payload


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    text = html.unescape(_TAG_RE.sub(" ", value))
    text = _SPACE_RE.sub(" ", text).strip()
    return text or None


def clean_title_candidate(value: str | None) -> str | None:
    if not value:
        return None
    candidate = unicodedata.normalize("NFKC", Path(value).stem)
    candidate = candidate.replace("_", " ")
    candidate = _RANGE_RE.sub(" ", candidate)
    candidate = _VERSION_RE.sub(" ", candidate)
    candidate = _BRACKET_RE.sub(" ", candidate)
    candidate = re.sub(r"\s*[-–—]\s*$", "", candidate)
    candidate = _SPACE_RE.sub(" ", candidate).strip(" ._-")
    return candidate if len(candidate) >= 2 else None


def language_name(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().casefold().replace("_", "-")
    if normalized in _LANGUAGE_NAMES:
        return _LANGUAGE_NAMES[normalized]
    primary = normalized.split("-", 1)[0]
    return _LANGUAGE_NAMES.get(primary, value.strip().title())


def detect_text_language(text: str) -> str | None:
    sample = text[:200_000]
    counts: Counter[str] = Counter()
    for char in sample:
        code = ord(char)
        if 0x0400 <= code <= 0x052F:
            counts["Russian"] += 1
        elif 0xAC00 <= code <= 0xD7AF or 0x1100 <= code <= 0x11FF:
            counts["Korean"] += 1
        elif 0x3040 <= code <= 0x30FF:
            counts["Japanese"] += 1
        elif 0x4E00 <= code <= 0x9FFF:
            counts["Chinese"] += 1
        elif "A" <= char <= "Z" or "a" <= char <= "z":
            counts["English"] += 1
    if not counts:
        return None
    language, count = counts.most_common(1)[0]
    meaningful = sum(counts.values())
    if count < 20 or count / max(meaningful, 1) < 0.2:
        return None
    if language == "Chinese" and counts["Japanese"] >= 5:
        return "Japanese"
    return language


def detect_original_language(title: str | None) -> str | None:
    if not title:
        return None
    language = detect_text_language(title)
    return language if language in {"Korean", "Japanese", "Chinese"} else None


def _epub_metadata(path: Path) -> tuple[dict[str, str | None], str]:
    metadata: dict[str, str | None] = {
        "title": None,
        "language": None,
        "description": None,
        "creator": None,
    }
    text_parts: list[str] = []
    inspected = 0
    with zipfile.ZipFile(path) as archive:
        rootfile = None
        try:
            container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
            for node in container.iter():
                if _local_name(node.tag) == "rootfile":
                    rootfile = node.attrib.get("full-path")
                    if rootfile:
                        break
        except (KeyError, ElementTree.ParseError):
            rootfile = None

        if rootfile:
            try:
                package = ElementTree.fromstring(archive.read(rootfile))
                for node in package.iter():
                    name = _local_name(node.tag)
                    value = _clean_text(node.text)
                    if name in metadata and value and not metadata[name]:
                        metadata[name] = value
            except (KeyError, ElementTree.ParseError):
                pass

        for name in archive.namelist():
            if inspected >= 4 * 1024 * 1024:
                break
            if not name.lower().endswith((".xhtml", ".html", ".htm", ".ncx", ".opf")):
                continue
            try:
                raw = archive.read(name)
            except (KeyError, RuntimeError):
                continue
            inspected += len(raw)
            text_parts.append(_clean_text(raw.decode("utf-8", errors="ignore")) or "")
    return metadata, "\n".join(text_parts)


def _pdf_metadata(path: Path) -> tuple[dict[str, str | None], str]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    info: Any = reader.metadata or {}
    metadata = {
        "title": _clean_text(str(info.get("/Title") or "")),
        "language": _clean_text(str(info.get("/Language") or "")),
        "description": _clean_text(str(info.get("/Subject") or "")),
        "creator": _clean_text(str(info.get("/Author") or "")),
    }
    text_parts: list[str] = []
    for index in range(min(len(reader.pages), 20)):
        try:
            text_parts.append(reader.pages[index].extract_text() or "")
        except Exception:
            continue
    text = "\n".join(text_parts)
    if not metadata["title"]:
        for line in text.splitlines()[:80]:
            candidate = clean_title_candidate(line)
            if candidate and len(candidate) <= 160 and not re.match(
                r"(?i)^(chapter|глава|contents|содержание)\b", candidate
            ):
                metadata["title"] = candidate
                break
    return metadata, text


def analyse_catalog_file(path: Path, kind: str, filename: str) -> AnalysedCatalogFile:
    detection = detect_chapter_range(path, kind, filename)
    if kind == "epub":
        metadata, text = _epub_metadata(path)
    elif kind == "pdf":
        metadata, text = _pdf_metadata(path)
    else:
        raise ValueError("Unsupported file kind")
    title = clean_title_candidate(metadata.get("title")) or clean_title_candidate(filename)
    declared_language = language_name(metadata.get("language"))
    return AnalysedCatalogFile(
        kind=kind,
        filename=filename,
        title=title,
        language=declared_language,
        text_language=detect_text_language(text),
        description=_clean_text(metadata.get("description")),
        creator=_clean_text(metadata.get("creator")),
        chapter_detection=detection,
    )


def merge_catalog_analysis(
    files: list[AnalysedCatalogFile], *, source_url: str | None = None
) -> dict[str, object]:
    titles = [item.title for item in files if item.title]
    display_title = titles[0] if titles else ""
    aliases = list(dict.fromkeys(title for title in titles if title and title != display_title))
    text_languages = [item.text_language for item in files if item.text_language]
    declared_languages = [item.language for item in files if item.language]
    translation_language = (
        Counter(text_languages).most_common(1)[0][0]
        if text_languages
        else (Counter(declared_languages).most_common(1)[0][0] if declared_languages else "Russian")
    )
    original_title = next(
        (title for title in titles if detect_original_language(title)),
        display_title,
    )
    original_language = detect_original_language(original_title) or ""

    detected = [
        item.chapter_detection
        for item in files
        if item.chapter_detection.chapter_start is not None
        and item.chapter_detection.chapter_end is not None
    ]
    chapter_start = detected[0].chapter_start if detected else None
    chapter_end = detected[0].chapter_end if detected else None
    warnings: list[str] = []

    ranges = {
        (item.chapter_start, item.chapter_end)
        for item in detected
        if item.chapter_start is not None and item.chapter_end is not None
    }
    if len(ranges) > 1:
        warnings.append("PDF и EPUB определили разные диапазоны глав. Проверьте значения.")
        best = sorted(
            detected,
            key=lambda item: (
                {"high": 3, "medium": 2, "low": 1, "none": 0}.get(item.confidence, 0),
                len(item.observed_chapters),
            ),
            reverse=True,
        )[0]
        chapter_start, chapter_end = best.chapter_start, best.chapter_end

    if not display_title:
        warnings.append("Название не удалось определить автоматически.")
    if not original_language:
        warnings.append("Язык оригинала не удалось определить по названию.")
    if chapter_start is None or chapter_end is None:
        warnings.append("Диапазон глав не найден в файлах или их названиях.")
    if len(set(titles)) > 1:
        warnings.append("В метаданных файлов указаны разные названия. Выберите правильное.")

    chapter_count = (
        chapter_end - chapter_start + 1
        if chapter_start is not None and chapter_end is not None
        else None
    )
    confidence = "high"
    if warnings:
        confidence = "medium" if display_title and chapter_count else "low"

    description = next((item.description for item in files if item.description), "") or ""
    return {
        "suggested": {
            "english_title": display_title,
            "original_title": original_title,
            "original_language": original_language,
            "translation_language": translation_language,
            "publication_status": "ongoing",
            "description": description,
            "source_url": source_url or "",
            "boosty_url": "",
            "aliases": aliases,
            "chapter_start": chapter_start,
            "chapter_end": chapter_end,
            "chapter_count": chapter_count,
            "display_name": (
                f"Chapters {chapter_start}–{chapter_end}"
                if chapter_start is not None and chapter_end is not None
                else ""
            ),
        },
        "confidence": confidence,
        "warnings": warnings,
        "files": [item.as_dict() for item in files],
    }
