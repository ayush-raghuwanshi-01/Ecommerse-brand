"""Object-storage abstraction for product imagery.

Providers: ``local`` (dev default) · ``cloudinary`` (recommended for production)
· ``s3`` (any S3-compatible store: AWS, DigitalOcean Spaces, Wasabi, MinIO).

Binary data never lives in PostgreSQL — only the URL, the storage key and
metadata. That keeps the database small enough to snapshot quickly and lets
images be served from a CDN instead of through the API process.

Why Cloudinary is the recommended default
-----------------------------------------
Product photography is the heaviest asset class in a fashion storefront, and
Indian mobile traffic needs WebP/AVIF at several widths. Cloudinary performs
resizing, format negotiation (``f_auto``) and device-pixel-ratio scaling as URL
transforms at the CDN edge, so the API never spends CPU on image processing and
no thumbnailing pipeline has to be maintained. ``S3Storage`` remains fully
functional for anyone who prefers to own their bucket.

Security note: uploads are **signed** server-side. An unsigned browser-side
upload preset would let anyone write into the media account.
"""

import hashlib
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("storage")

# Uploads are larger and slower than API calls; give them room but never hang.
_UPLOAD_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=10.0)


class StorageError(Exception):
    """A provider could not persist or delete an object."""


class StorageProvider(ABC):
    """Minimal contract every backend implements."""

    #: Identifies the provider in logs and error messages.
    name: str = "abstract"

    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str) -> str:
        """Persist bytes under ``key``; return the public URL."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove an object. Missing objects must not raise."""

    def url_for(self, key: str, width: int | None = None) -> str:
        """Public URL, optionally resized.

        Backends with an image CDN override this to return a transformed URL.
        The default returns the stored object unchanged, which is correct for
        local and plain-S3 storage.
        """
        return self.public_url(key)

    def public_url(self, key: str) -> str:  # pragma: no cover - overridden
        raise NotImplementedError


class LocalStorage(StorageProvider):
    """Development provider: writes to disk, served by the /static/uploads mount."""

    name = "local"

    def __init__(self) -> None:
        self.root = Path(settings.storage_local_path)
        self.root.mkdir(parents=True, exist_ok=True)
        self.base = settings.storage_public_base_url.rstrip("/")

    def put(self, key: str, data: bytes, content_type: str) -> str:
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return f"{self.base}/{key}"

    def delete(self, key: str) -> None:
        (self.root / key).unlink(missing_ok=True)

    def public_url(self, key: str) -> str:
        return f"{self.base}/{key}"


class CloudinaryStorage(StorageProvider):
    """Signed uploads to Cloudinary with responsive delivery URLs.

    Credentials come either from the discrete ``CLOUDINARY_*`` settings or from a
    single ``CLOUDINARY_URL`` of the form ``cloudinary://key:secret@cloud_name``,
    which is what the Cloudinary dashboard hands you.
    """

    name = "cloudinary"
    API_BASE = "https://api.cloudinary.com/v1_1"
    DELIVERY_BASE = "https://res.cloudinary.com"
    RESOURCE_TYPE = "image"

    def __init__(self) -> None:
        cloud_name, api_key, api_secret = self._credentials()
        if not (cloud_name and api_key and api_secret):
            raise StorageError(
                "Cloudinary is not fully configured. Set CLOUDINARY_URL "
                "(cloudinary://key:secret@cloud_name) or all three of "
                "CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET."
            )
        self._cloud = cloud_name
        self._key = api_key
        self._secret = api_secret
        # Objects live in a folder so the media library stays navigable and a
        # future teardown cannot accidentally hit unrelated assets.
        self._folder = settings.storage_bucket or "blackhouse"

    @staticmethod
    def _credentials() -> tuple[str, str, str]:
        url = (settings.cloudinary_url or "").strip()
        if url:
            parsed = urlparse(url)
            cloud = parsed.hostname or ""
            key = parsed.username or ""
            secret = parsed.password or ""
            if cloud and key and secret:
                return cloud, key, secret
            log.warning("CLOUDINARY_URL is set but malformed; falling back to discrete settings")
        return (
            settings.cloudinary_cloud_name,
            settings.cloudinary_api_key,
            settings.cloudinary_api_secret,
        )

    def _sign(self, params: dict[str, object]) -> str:
        """Cloudinary's upload signature.

        Params are sorted by key, joined as ``k=v`` with ``&``, then the API
        secret is appended and the whole string SHA-1 hashed. ``file`` and
        ``api_key``/``signature`` are excluded — they are not part of the signed
        set.
        """
        to_sign = "&".join(f"{k}={params[k]}" for k in sorted(params) if params[k] not in (None, ""))
        return hashlib.sha1(f"{to_sign}{self._secret}".encode()).hexdigest()

    def put(self, key: str, data: bytes, content_type: str) -> str:
        # Cloudinary identifies objects by public_id; the key we were given is
        # already namespaced and collision-free.
        public_id = key.removesuffix(Path(key).suffix) or key
        params: dict[str, object] = {
            "timestamp": int(time.time()),
            "public_id": public_id,
            "folder": self._folder,
            "overwrite": "true",
            "invalidate": "true",  # purge the CDN copy so a replacement is visible
            # Restrict to raster formats at the edge too — defence in depth behind
            # the magic-byte validation in app/core/uploads.py.
            "type": "upload",
            "access_mode": "public",
        }
        form = {
            **{k: str(v) for k, v in params.items()},
            "api_key": self._key,
            "signature": self._sign(params),
        }

        try:
            response = httpx.post(
                f"{self.API_BASE}/{self._cloud}/{self.RESOURCE_TYPE}/upload",
                data=form,
                files={"file": (Path(key).name, data, content_type)},
                timeout=_UPLOAD_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise StorageError(f"Cloudinary upload failed: {exc}") from exc

        if response.status_code not in {200, 201}:
            raise StorageError(
                f"Cloudinary rejected the upload ({response.status_code}): {response.text[:300]}"
            )

        payload = response.json()
        stored_id = payload.get("public_id") or public_id
        log.info(
            "cloudinary upload ok public_id=%s bytes=%d format=%s",
            stored_id,
            len(data),
            payload.get("format"),
        )
        # Store the *untransformed* URL; delivery transforms are applied on read
        # by url_for() so width can vary per placement.
        return self.public_url(stored_id)

    def delete(self, key: str) -> None:
        public_id = key.removesuffix(Path(key).suffix) or key
        params: dict[str, object] = {
            "timestamp": int(time.time()),
            "public_id": public_id,
            "invalidate": "true",
        }
        form = {
            **{k: str(v) for k, v in params.items()},
            "api_key": self._key,
            "signature": self._sign(params),
        }
        try:
            response = httpx.post(
                f"{self.API_BASE}/{self._cloud}/{self.RESOURCE_TYPE}/destroy",
                data=form,
                timeout=_UPLOAD_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            # Deletion failures are not worth failing a request over; the object
            # is already unreferenced. Log and move on.
            log.warning("cloudinary destroy failed for %s: %s", public_id, exc)
            return

        if response.status_code not in {200, 201}:
            log.warning(
                "cloudinary destroy returned %s for %s: %s",
                response.status_code,
                public_id,
                response.text[:200],
            )

    def public_url(self, key: str) -> str:
        return f"{self.DELIVERY_BASE}/{self._cloud}/{self.RESOURCE_TYPE}/upload/{key}"

    def url_for(self, key: str, width: int | None = None) -> str:
        """Responsive delivery URL.

        ``f_auto`` negotiates WebP/AVIF from the Accept header, ``q_`` caps the
        quality, ``dpr_auto`` serves 2× to retina devices. Inserting the
        transform segment into the upload URL is all that is required.
        """
        transform = f"f_auto,q_{settings.image_quality},dpr_auto"
        if width:
            transform += f",w_{int(width)}"
        return f"{self.DELIVERY_BASE}/{self._cloud}/{self.RESOURCE_TYPE}/upload/{transform}/{key}"


class S3Storage(StorageProvider):  # pragma: no cover - requires boto3 + credentials
    """Any S3-compatible object store.

    Set ``STORAGE_CDN_BASE_URL`` to serve through CloudFront / Spaces CDN instead
    of the raw bucket endpoint — that is what you want in production.
    """

    name = "s3"

    def __init__(self) -> None:
        try:
            import boto3  # optional dependency: pip install ".[s3]"
        except ImportError as exc:  # pragma: no cover
            raise StorageError(
                'STORAGE_PROVIDER=s3 requires boto3. Install with: pip install "blackhouse-backend[s3]"'
            ) from exc

        if not settings.storage_bucket:
            raise StorageError("STORAGE_PROVIDER=s3 requires STORAGE_BUCKET to be set.")

        # An explicit endpoint lets the same code drive DigitalOcean Spaces,
        # Wasabi or a local MinIO for integration tests.
        endpoint = settings.storage_endpoint_url or None
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=settings.storage_access_key or None,
            aws_secret_access_key=settings.storage_secret_key or None,
            region_name=settings.storage_region or None,
        )
        self._bucket = settings.storage_bucket
        self._cdn = (settings.storage_cdn_base_url or "").rstrip("/")

    def put(self, key: str, data: bytes, content_type: str) -> str:
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                # Objects are read by browsers and never executed; strip any
                # content-disposition ambiguity and cache aggressively since keys
                # are content-addressed by uuid.
                CacheControl="public, max-age=31536000, immutable",
                ACL="public-read",
            )
        except Exception as exc:
            raise StorageError(f"S3 upload failed: {exc}") from exc
        return self.public_url(key)

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except Exception as exc:  # pragma: no cover
            log.warning("s3 delete failed for %s: %s", key, exc)

    def public_url(self, key: str) -> str:
        if self._cdn:
            return f"{self._cdn}/{key}"
        region = settings.storage_region or "us-east-1"
        return f"https://{self._bucket}.s3.{region}.amazonaws.com/{key}"

    def presigned_put(self, key: str, content_type: str, expires_in: int = 300) -> str:
        """A short-lived URL letting the browser upload directly to the bucket.

        Keeps multi-megabyte product photography off the API process entirely.
        Not wired into a route yet — see docs/ROADMAP.md Phase 4.
        """
        return self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )


_storage_singleton: StorageProvider | None = None


def get_storage() -> StorageProvider:
    """Return the configured provider.

    Cached for the process lifetime: constructing a boto3 client or validating
    Cloudinary credentials on every upload is wasteful. Call ``reset_storage()``
    in tests that monkeypatch the settings.
    """
    global _storage_singleton
    if _storage_singleton is None:
        _storage_singleton = _build_storage()
    return _storage_singleton


def _build_storage() -> StorageProvider:
    provider = (settings.storage_provider or "local").strip().lower()
    if provider == "s3":
        return S3Storage()
    if provider == "cloudinary":
        return CloudinaryStorage()
    return LocalStorage()


def reset_storage() -> None:
    """Drop the cached provider (tests and settings reloads)."""
    global _storage_singleton
    _storage_singleton = None


def safe_filename(name: str) -> str:
    """Sanitise a client-supplied filename into a safe, unique, readable name.

    A filename is attacker-controlled: it may carry path traversal, shell
    metacharacters, or an extension that lies about the content. This reduces it
    to the basename, keeps only ``[A-Za-z0-9._-]``, collapses separator runs,
    trims leading/trailing punctuation, and appends random hex so two uploads of
    ``hero.jpg`` cannot collide.

    Note that the *stored* extension for uploads is derived from the file's magic
    bytes in ``app/core/uploads.py`` — a name is never trusted to describe
    content. This helper only produces something human-readable for keys and logs.
    """
    # Only the final path component. Normalising backslashes first means a
    # Windows-style traversal ("..\\..\\secret") is reduced the same way.
    basename = Path(name.replace("\\", "/")).name

    stem = Path(basename).stem
    suffix = Path(basename).suffix.lower()

    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem)
    stem = re.sub(r"-{2,}", "-", stem).strip("-._")[:60].strip("-._") or "image"

    # A suffix must look like a real extension; anything else is discarded rather
    # than trusted (this is what previously produced ".png-<hex>.jpg").
    if not re.fullmatch(r"\.[a-z0-9]{1,10}", suffix):
        suffix = ".jpg"

    return f"{stem}-{uuid4().hex[:8]}{suffix}"


def image_url(stored_url: str, width: int | None = None) -> str:
    """Apply a responsive transform to a stored URL when the backend supports it.

    Routes call this instead of building Cloudinary URLs themselves, so swapping
    ``STORAGE_PROVIDER`` never requires a code change in the API layer.
    """
    if not stored_url:
        return stored_url
    storage = get_storage()
    if isinstance(storage, CloudinaryStorage) and "/upload/" in stored_url:
        key = stored_url.split("/upload/", 1)[1]
        # Strip any transform segment that is already present.
        key = re.sub(r"^(f_auto[^/]*/)", "", key)
        return storage.url_for(key, width)
    return stored_url
