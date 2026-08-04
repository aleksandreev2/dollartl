from __future__ import annotations

import re
import unicodedata
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

_RANGE_PATTERNS = (
    re.compile(r"(?i)(?:chapters?|chs?|глав(?:ы|а)?)\s*[._ -]*(\d{1,6})\s*[-–—_]\s*(\d{1,6})"),
    re.compile(r"(?<!\d)(\d{1,6})\s*[-–—_]\s*(\d{1,6})(?!\d)"),
)
_CHAPTER_PATTERN = re.compile(
    r"(?i)(?:chapter|chap\.?|ch\.?|глава|гл\.?)\s*[:#№._ -]*([0-9]{1,6})"
)


@dataclass(frozen=True, slots=True)
class DetectionResult:
    chapter_start: int | None
    chapter_end: int | None
    source: str
    confidence: str
    observed_chapters: tuple[int, ...] = ()
    note: str | None = None

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["observed_chapters"] = list(self.observed_chapters)
        return payload


def _clean_filename(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", Path(name).stem)
    return normalized.replace("[", " ").replace("]", " ").replace("(", " ").replace(")", " ")


def detect_from_filename(name: str) -> DetectionResult:
    cleaned = _clean_filename(name)
    for pattern in _RANGE_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            start, end = sorted((int(match.group(1)), int(match.group(2))))
            return DetectionResult(start, end, "filename", "medium", (start, end))
    chapters = sorted({int(value) for value in _CHAPTER_PATTERN.findall(cleaned)})
    if chapters:
        return DetectionResult(chapters[0], chapters[-1], "filename", "low", tuple(chapters))
    return DetectionResult(None, None, "filename", "none", note="No chapter range in filename")


def _result_from_numbers(numbers: set[int], *, source: str) -> DetectionResult:
    filtered = sorted(number for number in numbers if 0 < number < 1_000_000)
    if not filtered:
        return DetectionResult(None, None, source, "none", note="No chapter headings detected")
    confidence = "high" if len(filtered) >= 3 else "medium"
    return DetectionResult(filtered[0], filtered[-1], source, confidence, tuple(filtered[:500]))


def detect_from_epub(path: Path) -> DetectionResult:
    numbers: set[int] = set()
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        for name in names:
            normalized = unicodedata.normalize("NFKC", name)
            numbers.update(int(value) for value in _CHAPTER_PATTERN.findall(normalized))
            for pattern in _RANGE_PATTERNS:
                match = pattern.search(normalized)
                if match:
                    numbers.update((int(match.group(1)), int(match.group(2))))

        inspected_bytes = 0
        for name in names:
            if inspected_bytes >= 12 * 1024 * 1024:
                break
            lower = name.lower()
            if not lower.endswith((".xhtml", ".html", ".htm", ".ncx", ".opf")):
                continue
            try:
                raw = archive.read(name)
            except (KeyError, RuntimeError):
                continue
            inspected_bytes += len(raw)
            text = raw.decode("utf-8", errors="ignore")
            numbers.update(int(value) for value in _CHAPTER_PATTERN.findall(text))
    return _result_from_numbers(numbers, source="epub")


def detect_from_pdf(path: Path) -> DetectionResult:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency is installed in production
        return DetectionResult(None, None, "pdf", "none", note=f"pypdf unavailable: {exc}")

    numbers: set[int] = set()
    reader = PdfReader(str(path))
    for index in range(min(len(reader.pages), 60)):
        page = reader.pages[index]
        try:
            text = page.extract_text() or ""
        except Exception:
            continue
        numbers.update(int(value) for value in _CHAPTER_PATTERN.findall(text))
    return _result_from_numbers(numbers, source="pdf")


def validate_file_signature(path: Path, file_kind: str) -> None:
    if file_kind == "pdf":
        with path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise ValueError("The uploaded file is not a valid PDF")
        return
    if file_kind == "epub":
        if not zipfile.is_zipfile(path):
            raise ValueError("The uploaded file is not a valid EPUB archive")
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "META-INF/container.xml" not in names:
                raise ValueError("EPUB is missing META-INF/container.xml")
        return
    raise ValueError("Unsupported file kind")


def detect_chapter_range(path: Path, file_kind: str, original_filename: str) -> DetectionResult:
    validate_file_signature(path, file_kind)
    content_result = detect_from_pdf(path) if file_kind == "pdf" else detect_from_epub(path)
    if content_result.chapter_start is not None:
        return content_result
    filename_result = detect_from_filename(original_filename)
    if filename_result.chapter_start is not None:
        return filename_result
    return content_result
