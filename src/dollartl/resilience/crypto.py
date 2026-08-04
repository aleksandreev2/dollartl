from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b"DTLBACKUP1\n"
HEADER_LENGTH = struct.Struct(">I")
CHUNK_HEADER = struct.Struct(">II")
DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class EncryptionResult:
    plaintext_size: int
    encrypted_size: int
    plaintext_sha256: str
    encrypted_sha256: str
    chunks: int


def hash_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _derive_key(secret: str, salt: bytes) -> bytes:
    if len(secret.encode("utf-8")) < 16:
        raise ValueError("BACKUP_ENCRYPTION_KEY must contain at least 16 bytes")
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"dollartl-backup-v1",
    ).derive(secret.encode("utf-8"))


def _write_header(destination: BinaryIO, header: dict[str, object]) -> bytes:
    raw = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    destination.write(MAGIC)
    destination.write(HEADER_LENGTH.pack(len(raw)))
    destination.write(raw)
    return raw


def _read_header(source: BinaryIO) -> tuple[dict[str, object], bytes]:
    if source.read(len(MAGIC)) != MAGIC:
        raise ValueError("Not a Dollar TL encrypted backup")
    length_raw = source.read(HEADER_LENGTH.size)
    if len(length_raw) != HEADER_LENGTH.size:
        raise ValueError("Backup header length is truncated")
    length = HEADER_LENGTH.unpack(length_raw)[0]
    if length < 2 or length > 1024 * 1024:
        raise ValueError("Backup header length is invalid")
    raw = source.read(length)
    if len(raw) != length:
        raise ValueError("Backup header is truncated")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("Unsupported backup format")
    return payload, raw


def encrypt_file(
    source_path: Path,
    destination_path: Path,
    secret: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> EncryptionResult:
    if chunk_size < 64 * 1024 or chunk_size > 64 * 1024 * 1024:
        raise ValueError("Invalid encryption chunk size")
    plaintext_size, plaintext_sha256 = hash_file(source_path)
    salt = os.urandom(16)
    nonce_prefix = os.urandom(8)
    header = {
        "algorithm": "AES-256-GCM-HKDF-SHA256",
        "chunk_size": chunk_size,
        "nonce_prefix": base64.b64encode(nonce_prefix).decode("ascii"),
        "plaintext_sha256": plaintext_sha256,
        "plaintext_size": plaintext_size,
        "salt": base64.b64encode(salt).decode("ascii"),
        "version": 1,
    }
    key = _derive_key(secret, salt)
    cipher = AESGCM(key)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    chunks = 0
    try:
        with source_path.open("rb") as source, destination_path.open("wb") as destination:
            header_raw = _write_header(destination, header)
            while plaintext := source.read(chunk_size):
                if chunks >= 2**32:
                    raise ValueError("Backup contains too many chunks")
                counter = chunks.to_bytes(4, "big")
                nonce = nonce_prefix + counter
                aad = MAGIC + header_raw + counter
                ciphertext = cipher.encrypt(nonce, plaintext, aad)
                destination.write(CHUNK_HEADER.pack(len(plaintext), len(ciphertext)))
                destination.write(ciphertext)
                chunks += 1
    except Exception:
        destination_path.unlink(missing_ok=True)
        raise
    encrypted_size, encrypted_sha256 = hash_file(destination_path)
    return EncryptionResult(
        plaintext_size=plaintext_size,
        encrypted_size=encrypted_size,
        plaintext_sha256=plaintext_sha256,
        encrypted_sha256=encrypted_sha256,
        chunks=chunks,
    )


def decrypt_file(source_path: Path, destination_path: Path, secret: str) -> EncryptionResult:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    chunks = 0
    written = 0
    actual_sha256 = ""
    try:
        with source_path.open("rb") as source:
            header, header_raw = _read_header(source)
            try:
                salt = base64.b64decode(str(header["salt"]), validate=True)
                nonce_prefix = base64.b64decode(str(header["nonce_prefix"]), validate=True)
                expected_size = int(header["plaintext_size"])
                expected_sha256 = str(header["plaintext_sha256"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Backup header fields are invalid") from exc
            if len(salt) != 16 or len(nonce_prefix) != 8:
                raise ValueError("Backup cryptographic parameters are invalid")
            cipher = AESGCM(_derive_key(secret, salt))
            digest = hashlib.sha256()
            with destination_path.open("wb") as destination:
                while True:
                    chunk_header = source.read(CHUNK_HEADER.size)
                    if not chunk_header:
                        break
                    if len(chunk_header) != CHUNK_HEADER.size:
                        raise ValueError("Backup chunk header is truncated")
                    plaintext_length, ciphertext_length = CHUNK_HEADER.unpack(chunk_header)
                    if plaintext_length < 1 or ciphertext_length != plaintext_length + 16:
                        raise ValueError("Backup chunk lengths are invalid")
                    ciphertext = source.read(ciphertext_length)
                    if len(ciphertext) != ciphertext_length:
                        raise ValueError("Backup chunk is truncated")
                    counter = chunks.to_bytes(4, "big")
                    plaintext = cipher.decrypt(
                        nonce_prefix + counter,
                        ciphertext,
                        MAGIC + header_raw + counter,
                    )
                    if len(plaintext) != plaintext_length:
                        raise ValueError("Backup chunk plaintext length is invalid")
                    destination.write(plaintext)
                    digest.update(plaintext)
                    written += len(plaintext)
                    chunks += 1
            actual_sha256 = digest.hexdigest()
            if written != expected_size or actual_sha256 != expected_sha256:
                raise ValueError("Backup plaintext checksum verification failed")
    except Exception:
        destination_path.unlink(missing_ok=True)
        raise
    encrypted_size, encrypted_sha256 = hash_file(source_path)
    return EncryptionResult(
        plaintext_size=written,
        encrypted_size=encrypted_size,
        plaintext_sha256=actual_sha256,
        encrypted_sha256=encrypted_sha256,
        chunks=chunks,
    )
