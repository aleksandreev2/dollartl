from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

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
    def upload_fileobj(
        self, fileobj: BinaryIO, key: str, content_type: str
    ) -> StoredObject:
        ...

    def download_file(self, key: str, destination: Path) -> Path:
        ...

    def delete(self, key: str) -> None:
        ...

    def exists(self, key: str) -> bool:
        ...


class S3Storage:
    def __init__(self, settings: Settings, bucket: str | None = None) -> None:
        self.bucket = bucket or settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id.get_secret_value(),
            aws_secret_access_key=settings.s3_secret_access_key.get_secret_value(),
            config=Config(
                s3={
                    "addressing_style": "path"
                    if settings.s3_force_path_style
                    else "auto"
                }
            ),
        )

    def upload_fileobj(self, fileobj: BinaryIO, key: str, content_type: str) -> StoredObject:
        self.client.upload_fileobj(fileobj, self.bucket, key, ExtraArgs={"ContentType": content_type})
        head = self.client.head_object(Bucket=self.bucket, Key=key)
        return StoredObject(key=key, size=int(head["ContentLength"]), etag=head.get("ETag"))

    def download_file(self, key: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(destination))
        return destination

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError:
            return False
        return True
