from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from types_boto3_s3 import S3Client

from supply_chain_hub.settings.config import get_settings


class ObjectStorageError(Exception):
    """Base error for S3-compatible object operations."""


class ObjectNotFoundError(ObjectStorageError):
    """The requested object does not exist."""


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    size_bytes: int
    etag: str


class ObjectStore(Protocol):
    def put(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str,
        sha256: str,
    ) -> StoredObject: ...

    def get(self, key: str) -> bytes: ...

    def list_keys(self, prefix: str) -> list[str]: ...

    def is_available(self) -> bool: ...


class S3ObjectStore:
    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str,
    ) -> None:
        self.bucket = bucket
        self._client: S3Client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=3,
                read_timeout=10,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )

    def put(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str,
        sha256: str,
    ) -> StoredObject:
        try:
            response = self._client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
                Metadata={"sha256": sha256},
            )
            head = self._client.head_object(Bucket=self.bucket, Key=key)
        except (BotoCoreError, ClientError) as error:
            raise ObjectStorageError(f"Could not store object '{key}'.") from error
        size_bytes = int(head["ContentLength"])
        if size_bytes != len(content):
            raise ObjectStorageError(
                f"Stored object '{key}' has an unexpected content length."
            )
        return StoredObject(
            key=key,
            size_bytes=size_bytes,
            etag=str(response.get("ETag", "")).strip('"'),
        )

    def get(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
            body = response["Body"]
            return bytes(body.read())
        except ClientError as error:
            error_code = str(error.response.get("Error", {}).get("Code", ""))
            if error_code in {"NoSuchKey", "404", "NotFound"}:
                raise ObjectNotFoundError(f"Object '{key}' was not found.") from error
            raise ObjectStorageError(f"Could not read object '{key}'.") from error
        except BotoCoreError as error:
            raise ObjectStorageError(f"Could not read object '{key}'.") from error

    def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        continuation_token: str | None = None
        try:
            while True:
                if continuation_token is None:
                    response = self._client.list_objects_v2(
                        Bucket=self.bucket,
                        Prefix=prefix,
                    )
                else:
                    response = self._client.list_objects_v2(
                        Bucket=self.bucket,
                        Prefix=prefix,
                        ContinuationToken=continuation_token,
                    )
                keys.extend(
                    str(item["Key"])
                    for item in response.get("Contents", [])
                    if "Key" in item
                )
                if not response.get("IsTruncated"):
                    return sorted(keys)
                continuation_token = str(response["NextContinuationToken"])
        except (BotoCoreError, ClientError) as error:
            raise ObjectStorageError(
                f"Could not list objects under '{prefix}'."
            ) from error

    def is_available(self) -> bool:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except (BotoCoreError, ClientError):
            return False
        return True


@lru_cache
def get_object_store() -> ObjectStore:
    settings = get_settings()
    return S3ObjectStore(
        endpoint=settings.object_storage_endpoint,
        access_key=settings.object_storage_access_key,
        secret_key=settings.object_storage_secret_key,
        bucket=settings.object_storage_bucket,
        region=settings.object_storage_region,
    )


def object_store_is_available() -> bool:
    return get_object_store().is_available()
