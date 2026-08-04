from __future__ import annotations

from pathlib import Path

import pytest

from dollartl.resilience.crypto import decrypt_file, encrypt_file


def test_backup_encryption_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "database.dump"
    encrypted = tmp_path / "database.dtlbak"
    restored = tmp_path / "restored.dump"
    source.write_bytes((b"Dollar TL backup data\n" * 10000) + bytes(range(256)))

    encrypted_result = encrypt_file(source, encrypted, "correct horse battery staple")
    decrypted_result = decrypt_file(
        encrypted,
        restored,
        "correct horse battery staple",
    )

    assert restored.read_bytes() == source.read_bytes()
    assert encrypted_result.plaintext_sha256 == decrypted_result.plaintext_sha256
    assert encrypted_result.plaintext_size == source.stat().st_size
    assert encrypted.read_bytes() != source.read_bytes()


def test_backup_tampering_is_detected(tmp_path: Path) -> None:
    source = tmp_path / "database.dump"
    encrypted = tmp_path / "database.dtlbak"
    restored = tmp_path / "restored.dump"
    source.write_bytes(b"critical database data" * 1000)
    encrypt_file(source, encrypted, "correct horse battery staple")

    payload = bytearray(encrypted.read_bytes())
    payload[-1] ^= 0x01
    encrypted.write_bytes(payload)

    with pytest.raises(Exception):
        decrypt_file(encrypted, restored, "correct horse battery staple")
    assert not restored.exists()


def test_wrong_backup_key_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "database.dump"
    encrypted = tmp_path / "database.dtlbak"
    restored = tmp_path / "restored.dump"
    source.write_bytes(b"database")
    encrypt_file(source, encrypted, "correct horse battery staple")

    with pytest.raises(Exception):
        decrypt_file(encrypted, restored, "totally different backup key")
    assert not restored.exists()


def test_short_backup_key_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "database.dump"
    destination = tmp_path / "backup.dtlbak"
    source.write_bytes(b"database")
    with pytest.raises(ValueError, match="at least 16 bytes"):
        encrypt_file(source, destination, "short")
    assert not destination.exists()
