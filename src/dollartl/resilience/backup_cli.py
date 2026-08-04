from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path

from dollartl.config import get_settings
from dollartl.resilience.crypto import decrypt_file, encrypt_file


def _secret() -> str:
    value = get_settings().backup_encryption_key.get_secret_value()
    if not value:
        raise SystemExit("BACKUP_ENCRYPTION_KEY is required")
    return value


def _run(*arguments: str) -> str:
    result = subprocess.run(
        arguments,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"{arguments[0]} failed ({result.returncode}):\n{result.stderr[-4000:]}"
        )
    return result.stdout


def encrypt_command(source: Path, destination: Path) -> None:
    result = encrypt_file(source, destination, _secret())
    print(json.dumps(asdict(result), indent=2, sort_keys=True))


def decrypt_command(source: Path, destination: Path) -> None:
    result = decrypt_file(source, destination, _secret())
    print(json.dumps(asdict(result), indent=2, sort_keys=True))


def verify_command(source: Path, restore_dsn: str | None) -> None:
    with tempfile.TemporaryDirectory(prefix="dollartl-verify-") as temporary:
        dump = Path(temporary) / "database.dump"
        result = decrypt_file(source, dump, _secret())
        listing = _run("pg_restore", "--list", str(dump))
        entries = sum(
            1 for line in listing.splitlines() if line and not line.startswith(";")
        )
        if entries < 1:
            raise SystemExit("The PostgreSQL archive contains no restore entries")
        restored = False
        if restore_dsn:
            _run(
                "pg_restore",
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-acl",
                "--exit-on-error",
                f"--dbname={restore_dsn}",
                str(dump),
            )
            _run(
                "psql",
                restore_dsn,
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                "SELECT version_num FROM alembic_version;",
            )
            restored = True
        print(
            json.dumps(
                {
                    **asdict(result),
                    "archive_entries": entries,
                    "restore_verified": restored,
                },
                indent=2,
                sort_keys=True,
            )
        )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Dollar TL encrypted backup utility")
    commands = root.add_subparsers(dest="command", required=True)

    encrypt_parser = commands.add_parser("encrypt")
    encrypt_parser.add_argument("source", type=Path)
    encrypt_parser.add_argument("destination", type=Path)

    decrypt_parser = commands.add_parser("decrypt")
    decrypt_parser.add_argument("source", type=Path)
    decrypt_parser.add_argument("destination", type=Path)

    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("source", type=Path)
    verify_parser.add_argument(
        "--restore-dsn",
        default=get_settings().backup_verify_dsn.get_secret_value() or None,
        help="Dedicated disposable PostgreSQL database that may be wiped",
    )
    return root


def main() -> None:
    arguments = parser().parse_args()
    if arguments.command == "encrypt":
        encrypt_command(arguments.source, arguments.destination)
    elif arguments.command == "decrypt":
        decrypt_command(arguments.source, arguments.destination)
    else:
        verify_command(arguments.source, arguments.restore_dsn)


if __name__ == "__main__":
    main()
