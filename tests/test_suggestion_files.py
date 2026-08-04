import io
import zipfile

import pytest

from dollartl.services.suggestion_files import inspect_upload


def make_zip(name: str = "chapter-1.txt", payload: bytes = b"Chapter 1") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, payload)
    return buffer.getvalue()


def test_safe_zip_passes() -> None:
    result = inspect_upload(
        filename="raw.zip",
        data=make_zip(),
        file_kind="raw",
        max_bytes=20 * 1024 * 1024,
        archive_max_entries=500,
        archive_max_unpacked_bytes=200 * 1024 * 1024,
    )
    assert result.status == "valid"


def test_zip_traversal_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsafe path"):
        inspect_upload(
            filename="raw.zip",
            data=make_zip("../secret.txt"),
            file_kind="raw",
            max_bytes=20 * 1024 * 1024,
            archive_max_entries=500,
            archive_max_unpacked_bytes=200 * 1024 * 1024,
        )
