#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from dollartl.config import get_settings


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def boolean(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def client(
    *, endpoint: str | None, region: str, access_key: str, secret_key: str, path_style: bool
):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(s3={"addressing_style": "path" if path_style else "auto"}),
    )


def hash_object(s3: Any, bucket: str, key: str) -> str:
    response = s3.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    digest = hashlib.sha256()
    try:
        while chunk := body.read(1024 * 1024):
            digest.update(chunk)
    finally:
        body.close()
    return digest.hexdigest()


def head(s3: Any, bucket: str, key: str) -> dict[str, Any] | None:
    try:
        return dict(s3.head_object(Bucket=bucket, Key=key))
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Copy Dollar TL S3 objects between independent providers/accounts"
    )
    root.add_argument("mode", choices=["copy", "verify"])
    root.add_argument("--manifest", type=Path)
    root.add_argument("--prefix", default="")
    root.add_argument("--destination-prefix", default="")
    root.add_argument("--report", type=Path, default=Path("backup-exports/storage-transfer-report.json"))
    root.add_argument("--verify-content-hash", action="store_true")
    return root


def load_objects(arguments: argparse.Namespace, source: Any, source_bucket: str) -> list[dict[str, Any]]:
    if arguments.manifest:
        payload = json.loads(arguments.manifest.read_text(encoding="utf-8"))
        return [dict(item) for item in payload.get("objects", [])]
    objects: list[dict[str, Any]] = []
    paginator = source.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=source_bucket, Prefix=arguments.prefix):
        for item in page.get("Contents", []):
            objects.append(
                {
                    "key": str(item["Key"]),
                    "size": int(item["Size"]),
                    "etag": str(item.get("ETag", "")).strip('"'),
                    "sha256": None,
                }
            )
    return objects


def main() -> None:
    arguments = parser().parse_args()
    settings = get_settings()
    source = client(
        endpoint=settings.s3_endpoint_url,
        region=settings.s3_region,
        access_key=settings.s3_access_key_id.get_secret_value(),
        secret_key=settings.s3_secret_access_key.get_secret_value(),
        path_style=settings.s3_force_path_style,
    )
    destination = client(
        endpoint=os.getenv("DEST_S3_ENDPOINT_URL") or None,
        region=os.getenv("DEST_S3_REGION", "auto"),
        access_key=required("DEST_S3_ACCESS_KEY_ID"),
        secret_key=required("DEST_S3_SECRET_ACCESS_KEY"),
        path_style=boolean("DEST_S3_FORCE_PATH_STYLE", True),
    )
    destination_bucket = required("DEST_S3_BUCKET")
    source.head_bucket(Bucket=settings.s3_bucket)
    destination.head_bucket(Bucket=destination_bucket)
    objects = load_objects(arguments, source, settings.s3_bucket)
    report: list[dict[str, Any]] = []
    copied = 0
    copied_bytes = 0
    failures = 0

    for item in objects:
        source_key = str(item["key"])
        destination_key = f"{arguments.destination_prefix}{source_key}"
        expected_size = int(item.get("size", 0))
        expected_etag = str(item.get("etag") or "").strip('"')
        expected_sha256 = item.get("sha256")
        destination_head = head(destination, destination_bucket, destination_key)
        destination_metadata = (destination_head or {}).get("Metadata", {})
        current = bool(
            destination_head
            and int(destination_head.get("ContentLength", -1)) == expected_size
            and destination_metadata.get("source-etag") == expected_etag
            and destination_metadata.get("source-size") == str(expected_size)
        )
        copied_now = False
        error: str | None = None
        try:
            if arguments.mode == "copy" and not current:
                response = source.get_object(Bucket=settings.s3_bucket, Key=source_key)
                body = response["Body"]
                try:
                    destination.upload_fileobj(
                        body,
                        destination_bucket,
                        destination_key,
                        ExtraArgs={
                            "ContentType": response.get("ContentType") or "application/octet-stream",
                            "Metadata": {
                                "source-etag": expected_etag,
                                "source-size": str(expected_size),
                            },
                        },
                    )
                finally:
                    body.close()
                copied += 1
                copied_bytes += expected_size
                copied_now = True
            final_head = head(destination, destination_bucket, destination_key)
            verified = bool(
                final_head and int(final_head.get("ContentLength", -1)) == expected_size
            )
            actual_sha256: str | None = None
            if verified and arguments.verify_content_hash and expected_sha256:
                actual_sha256 = hash_object(destination, destination_bucket, destination_key)
                verified = actual_sha256 == expected_sha256
            if not verified:
                failures += 1
        except Exception as exc:
            verified = False
            actual_sha256 = None
            failures += 1
            error = f"{type(exc).__name__}: {exc}"[:2000]
        report.append(
            {
                "source_key": source_key,
                "destination_key": destination_key,
                "size": expected_size,
                "copied": copied_now,
                "verified": verified,
                "expected_sha256": expected_sha256,
                "actual_sha256": actual_sha256,
                "error": error,
            }
        )

    payload = {
        "format_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": arguments.mode,
        "source_bucket": settings.s3_bucket,
        "destination_bucket": destination_bucket,
        "object_count": len(objects),
        "copied_count": copied,
        "copied_bytes": copied_bytes,
        "failure_count": failures,
        "objects": report,
    }
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(arguments.report)
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
