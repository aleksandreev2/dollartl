#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config

from dollartl.config import get_settings


def hash_object(client: Any, bucket: str, key: str) -> str:
    response = client.get_object(Bucket=bucket, Key=key)
    digest = hashlib.sha256()
    body = response["Body"]
    try:
        while chunk := body.read(1024 * 1024):
            digest.update(chunk)
    finally:
        body.close()
    return digest.hexdigest()


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Export a checksummed Dollar TL S3 manifest")
    root.add_argument(
        "--output",
        type=Path,
        default=Path("backup-exports/object-manifest.json"),
    )
    root.add_argument("--prefix", default="")
    root.add_argument(
        "--skip-content-hash",
        action="store_true",
        help="Use only size and ETag for a faster, weaker inventory",
    )
    return root


def main() -> None:
    arguments = parser().parse_args()
    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        config=Config(
            s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"}
        ),
    )
    output = arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    objects: list[dict[str, Any]] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.s3_bucket, Prefix=arguments.prefix):
        for item in page.get("Contents", []):
            key = str(item["Key"])
            objects.append(
                {
                    "key": key,
                    "size": int(item["Size"]),
                    "etag": str(item.get("ETag", "")).strip('"'),
                    "last_modified": item["LastModified"].isoformat(),
                    "sha256": None
                    if arguments.skip_content_hash
                    else hash_object(client, settings.s3_bucket, key),
                }
            )
    payload = {
        "format_version": 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "bucket": settings.s3_bucket,
        "endpoint": settings.s3_endpoint_url,
        "prefix": arguments.prefix,
        "object_count": len(objects),
        "total_bytes": sum(item["size"] for item in objects),
        "objects": objects,
    }
    raw = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    output.write_bytes(raw)
    output.with_suffix(output.suffix + ".sha256").write_text(
        hashlib.sha256(raw).hexdigest() + "  " + output.name + "\n",
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
