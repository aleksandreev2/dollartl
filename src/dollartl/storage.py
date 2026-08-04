from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Iterator, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from dollartl.config import Settings


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    size: int
    etag: str | None


class StorageAdapter(Protocol):
    def upload_fileobj(self, fileobj: BinaryIO, key: str, content_type: str) -> StoredObject: ...
    def download_file(self, key: str, destination: Path) -> Path: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
    def presigned_get_url(self, key: str, *, expires_seconds: int = 300, filename: str | None = None) -> str: ...


class S3Storage:
    def __init__(
        self,
        settings: Settings,
        bucket: str | None = None,
        *,
        endpoint_url: str | None = None,
        region: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        force_path_style: bool | None = None,
    ) -> None:
        self.bucket = bucket or settings.s3_bucket
        path_style = settings.s3_force_path_style if force_path_style is None else force_path_style
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url if endpoint_url is None else endpoint_url,
            region_name=region or settings.s3_region,
            aws_access_key_id=access_key_id or settings.s3_access_key_id.get_secret_value(),
            aws_secret_access_key=secret_access_key or settings.s3_secret_access_key.get_secret_value(),
            config=Config(s3={"addressing_style": "path" if path_style else "auto"}),
        )

    @classmethod
    def backup(cls, settings: Settings) -> S3Storage:
        return cls(
            settings,
            bucket=settings.s3_backup_bucket,
            endpoint_url=settings.effective_backup_s3_endpoint_url,
            region=settings.effective_backup_s3_region,
            access_key_id=settings.effective_backup_s3_access_key_id,
            secret_access_key=settings.effective_backup_s3_secret_access_key,
            force_path_style=settings.effective_backup_s3_force_path_style,
        )

    def upload_fileobj(self, fileobj: BinaryIO, key: str, content_type: str) -> StoredObject:
        self.client.upload_fileobj(fileobj, self.bucket, key, ExtraArgs={"ContentType": content_type})
        head = self.client.head_object(Bucket=self.bucket, Key=key)
        return StoredObject(key=key, size=int(head["ContentLength"]), etag=head.get("ETag"))

    def upload_path(self, path: Path, key: str, content_type: str) -> StoredObject:
        with path.open("rb") as stream:
            return self.upload_fileobj(stream, key, content_type)

    def download_file(self, key: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(destination))
        return destination

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def delete_many(self, keys: list[str]) -> None:
        for offset in range(0, len(keys), 1000):
            chunk = keys[offset : offset + 1000]
            if not chunk:
                continue
            response = self.client.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": [{"Key": key} for key in chunk], "Quiet": True},
            )
            errors = response.get("Errors", [])
            if errors:
                summary = ", ".join(
                    f"{item.get('Key', '?')}:{item.get('Code', 'Unknown')}"
                    for item in errors[:20]
                )
                raise RuntimeError(f"S3 failed to delete one or more objects: {summary}")

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError:
            return False
        return True

    def head(self, key: str) -> dict[str, Any] | None:
        try:
            return dict(self.client.head_object(Bucket=self.bucket, Key=key))
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise

    def iter_objects(self, prefix: str = "") -> Iterator[dict[str, Any]]:
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                yield dict(item)

    def ensure_bucket_access(self) -> None:
        self.client.head_bucket(Bucket=self.bucket)

    def presigned_get_url(
        self,
        key: str,
        *,
        expires_seconds: int = 300,
        filename: str | None = None,
    ) -> str:
        params: dict[str, str] = {"Bucket": self.bucket, "Key": key}
        if filename:
            safe = filename.replace('"', "").replace("\r", "").replace("\n", "")
            params["ResponseContentDisposition"] = f'attachment; filename="{safe}"'
        return str(
            self.client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=max(60, min(expires_seconds, 7 * 24 * 60 * 60)),
            )
        )
