"""Object-storage abstraction for product imagery.

Providers: local (dev default) | s3 (S3-compatible) | cloudinary (interface).
Binary data never lives in PostgreSQL — only URL + storage key + metadata.
"""

import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings


class StorageProvider(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str) -> str:
        """Persist bytes; return public URL."""

    @abstractmethod
    def delete(self, key: str) -> None: ...


class LocalStorage(StorageProvider):
    def __init__(self) -> None:
        self.root = Path(settings.storage_local_path)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, data: bytes, content_type: str) -> str:
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return f"/static/uploads/{key}"

    def delete(self, key: str) -> None:
        (self.root / key).unlink(missing_ok=True)


class S3Storage(StorageProvider):  # pragma: no cover - requires boto3 + credentials
    def __init__(self) -> None:
        import boto3  # optional dependency

        self._client = boto3.client(
            "s3",
            aws_access_key_id=settings.storage_access_key,
            aws_secret_access_key=settings.storage_secret_key,
            region_name=settings.storage_region or None,
        )
        self._bucket = settings.storage_bucket

    def put(self, key: str, data: bytes, content_type: str) -> str:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)
        return f"https://{self._bucket}.s3.{settings.storage_region}.amazonaws.com/{key}"

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


class CloudinaryStorage(StorageProvider):  # pragma: no cover - interface until chosen
    def put(self, key: str, data: bytes, content_type: str) -> str:
        from app.core.exceptions import ProviderNotConfiguredError

        raise ProviderNotConfiguredError("Cloudinary provider not configured yet.")

    def delete(self, key: str) -> None: ...


def get_storage() -> StorageProvider:
    if settings.storage_provider == "s3":
        return S3Storage()
    if settings.storage_provider == "cloudinary":
        return CloudinaryStorage()
    return LocalStorage()


def safe_filename(name: str) -> str:
    import re
    from uuid import uuid4

    stem = re.sub(r"[^A-Za-z0-9._-]", "-", Path(name).stem)[:60] or "image"
    return f"{stem}-{uuid4().hex[:8]}{Path(name).suffix.lower() or '.jpg'}"


_ = shutil  # re-export guard for tooling
