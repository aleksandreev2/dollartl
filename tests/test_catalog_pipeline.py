from pathlib import Path
import zipfile

from dollartl.files.catalog_metadata import (
    analyse_catalog_file,
    clean_title_candidate,
    detect_text_language,
    merge_catalog_analysis,
)


def _write_epub(path: Path) -> None:
    container = """<?xml version="1.0"?>
    <container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
      <rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles>
    </container>"""
    package = """<?xml version="1.0"?>
    <package xmlns="http://www.idpf.org/2007/opf"
             xmlns:dc="http://purl.org/dc/elements/1.1/">
      <metadata>
        <dc:title>Моя дочь — финальный босс</dc:title>
        <dc:language>ru</dc:language>
        <dc:description>Тестовое описание</dc:description>
      </metadata>
    </package>"""
    chapter = "<html><body><h1>Глава 21</h1><p>Это русский текст перевода.</p><h1>Глава 40</h1></body></html>"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OEBPS/content.opf", package)
        archive.writestr("OEBPS/chapter21.xhtml", chapter)


def test_title_cleanup_removes_range_and_format() -> None:
    assert clean_title_candidate("Моя дочь — финальный босс — Главы 21-40 EPUB.epub") == "Моя дочь — финальный босс"


def test_text_language_detection() -> None:
    assert detect_text_language("Это длинный русский текст для надёжного определения языка. " * 5) == "Russian"
    assert detect_text_language("한국어 문장입니다. 이것은 테스트 텍스트입니다. " * 5) == "Korean"


def test_epub_pipeline_analysis(tmp_path: Path) -> None:
    path = tmp_path / "Моя дочь — финальный босс Главы 21-40.epub"
    _write_epub(path)
    item = analyse_catalog_file(path, "epub", path.name)
    payload = merge_catalog_analysis([item])
    suggested = payload["suggested"]

    assert suggested["english_title"] == "Моя дочь — финальный босс"
    assert suggested["translation_language"] == "Russian"
    assert suggested["chapter_start"] == 21
    assert suggested["chapter_end"] == 40
    assert suggested["chapter_count"] == 20
