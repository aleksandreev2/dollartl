#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import boto3

from dollartl.config import get_settings


def client(
    *, endpoint: str | None, region: str, access_key: str, secret_key: str
) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--source-bucket", required=True)
    args = parser.parse_args()
    settings = get_settings()
    source = client(
        endpoint=os.getenv("SOURCE_S3_ENDPOINT_URL"),
        region=os.getenv("SOURCE_S3_REGION", "auto"),
        access_key=os.environ["SOURCE_S3_ACCESS_KEY_ID"],
        secret_key=os.environ["SOURCE_S3_SECRET_ACCESS_KEY"],
    )
    destination = client(
        endpoint=settings.s3_endpoint_url,
        region=settings.s3_region,
        access_key=settings.s3_access_key_id.get_secret_value(),
        secret_key=settings.s3_secret_access_key.get_secret_value(),
    )
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    for item in manifest["objects"]:
        key = item["key"]
        with tempfile.NamedTemporaryFile() as temporary:
            source.download_file(args.source_bucket, key, temporary.name)
            path = Path(temporary.name)
            actual = sha256(path)
            if actual != item["sha256"]:
                raise RuntimeError(f"Checksum mismatch for {key}")
            destination.upload_file(str(path), settings.s3_bucket, key)
    print(f"Copied {len(manifest['objects'])} verified objects to {settings.s3_bucket}")


if __name__ == "__main__":
    main()
