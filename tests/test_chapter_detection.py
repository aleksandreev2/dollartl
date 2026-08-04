from pathlib import Path
import zipfile

from dollartl.files.chapter_detection import detect_chapter_range, detect_from_filename


def test_detect_range_from_filename() -> None:
    result = detect_from_filename("Novel Chapters 21-40.epub")
    assert (result.chapter_start, result.chapter_end) == (21, 40)


def test_detect_range_from_epub(tmp_path: Path) -> None:
    path = tmp_path / "book.epub"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("META-INF/container.xml", "<container />")
        archive.writestr("OEBPS/chapter_21.xhtml", "<h1>Chapter 21</h1>")
        archive.writestr("OEBPS/chapter_22.xhtml", "<h1>Chapter 22</h1>")
        archive.writestr("OEBPS/chapter_23.xhtml", "<h1>Chapter 23</h1>")
    result = detect_chapter_range(path, "epub", "book.epub")
    assert (result.chapter_start, result.chapter_end) == (21, 23)
    assert result.confidence == "high"


def test_reject_fake_epub(tmp_path: Path) -> None:
    path = tmp_path / "fake.epub"
    path.write_text("not a zip", encoding="utf-8")
    try:
        detect_chapter_range(path, "epub", "fake.epub")
    except ValueError as exc:
        assert "valid EPUB" in str(exc)
    else:
        raise AssertionError("fake EPUB was accepted")
