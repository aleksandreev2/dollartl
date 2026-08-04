#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import boto3

from dollartl.config import get_settings


def hash_object(client: Any, bucket: str, key: str) -> str:
    response = client.get_object(Bucket=bucket, Key=key)
    digest = hashlib.sha256()
    body = response["Body"]
    while chunk := body.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_access_key.get_secret_value(),
    )
    output = Path("backup-exports/object-manifest.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    objects: list[dict[str, Any]] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.s3_bucket):
        for item in page.get("Contents", []):
            key = item["Key"]
            objects.append(
                {
                    "key": key,
                    "size": item["Size"],
                    "etag": item.get("ETag"),
                    "sha256": hash_object(client, settings.s3_bucket, key),
                }
            )
    payload = {"bucket": settings.s3_bucket, "objects": objects}
    raw = json.dumps(payload, indent=2, sort_keys=True).encode()
    output.write_bytes(raw)
    output.with_suffix(".json.sha256").write_text(
        hashlib.sha256(raw).hexdigest() + "  " + output.name + "\n",
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
