from __future__ import annotations

import os
from pathlib import Path

import boto3
from botocore.config import Config


class PipelineObjectStore:
    def __init__(self) -> None:
        self.bucket = os.environ.get("OBJECT_STORAGE_BUCKET", "supply-chain-data")
        self._client = boto3.client(
            "s3",
            endpoint_url=os.environ.get(
                "OBJECT_STORAGE_ENDPOINT",
                "http://object-store:8333",
            ),
            aws_access_key_id=os.environ.get(
                "OBJECT_STORAGE_ACCESS_KEY",
                "supply-chain-local",
            ),
            aws_secret_access_key=os.environ.get(
                "OBJECT_STORAGE_SECRET_KEY",
                "local-object-storage-only",
            ),
            region_name=os.environ.get("OBJECT_STORAGE_REGION", "us-east-1"),
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

    def put_bytes(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str,
    ) -> None:
        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )

    def get_bytes(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        return bytes(response["Body"].read())

    def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(str(item["Key"]) for item in page.get("Contents", []))
        return sorted(keys)

    def download_prefix(self, prefix: str, destination: Path) -> list[Path]:
        downloaded: list[Path] = []
        for key in self.list_keys(prefix):
            relative = key.removeprefix(prefix).lstrip("/")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            self._client.download_file(self.bucket, key, str(target))
            downloaded.append(target)
        return downloaded

    def upload_directory(
        self,
        source: Path,
        destination_prefix: str,
    ) -> list[str]:
        uploaded: list[str] = []
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            if path.name.startswith("."):
                continue
            relative = path.relative_to(source).as_posix()
            key = f"{destination_prefix.rstrip('/')}/{relative}"
            self._client.upload_file(str(path), self.bucket, key)
            uploaded.append(key)
        return uploaded
