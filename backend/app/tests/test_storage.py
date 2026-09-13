"""Storage provider tests.

No network access: Cloudinary is exercised through a mocked httpx transport, and
S3 through a stubbed boto3 client. The signature algorithm is verified against a
hand-computed SHA-1 so a regression cannot silently break every upload.
"""

import hashlib
import re
from typing import Any

import httpx
import pytest

from app.core.config import settings
from app.services import storage_service
from app.services.storage_service import (
    CloudinaryStorage,
    LocalStorage,
    StorageError,
    get_storage,
    image_url,
    reset_storage,
    safe_filename,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    """get_storage() caches for the process; tests monkeypatch settings."""
    reset_storage()
    yield
    reset_storage()


@pytest.fixture()
def cloudinary_env(monkeypatch):
    monkeypatch.setattr(settings, "storage_provider", "cloudinary", raising=False)
    monkeypatch.setattr(settings, "cloudinary_url", "", raising=False)
    monkeypatch.setattr(settings, "cloudinary_cloud_name", "blackhouse", raising=False)
    monkeypatch.setattr(settings, "cloudinary_api_key", "123456789", raising=False)
    monkeypatch.setattr(settings, "cloudinary_api_secret", "s3cr3t", raising=False)
    monkeypatch.setattr(settings, "storage_bucket", "products", raising=False)
    monkeypatch.setattr(settings, "image_quality", 80, raising=False)
    yield


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or str(self._payload)

    def json(self) -> Any:
        return self._payload


# ══════════════════════════════════════════════════════════════════════════
# Provider selection
# ══════════════════════════════════════════════════════════════════════════


def test_local_is_the_default(monkeypatch):
    monkeypatch.setattr(settings, "storage_provider", "local", raising=False)
    assert isinstance(get_storage(), LocalStorage)


def test_provider_is_cached_across_calls(cloudinary_env):
    first = get_storage()
    assert get_storage() is first, "constructing a client per upload is wasteful"


def test_reset_storage_rebuilds(cloudinary_env):
    first = get_storage()
    reset_storage()
    assert get_storage() is not first


def test_unknown_provider_falls_back_to_local(monkeypatch):
    monkeypatch.setattr(settings, "storage_provider", "carrier-pigeon", raising=False)
    assert isinstance(get_storage(), LocalStorage)


# ══════════════════════════════════════════════════════════════════════════
# Local storage
# ══════════════════════════════════════════════════════════════════════════


def test_local_put_writes_and_returns_served_url(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_local_path", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "storage_public_base_url", "/static/uploads", raising=False)

    storage = LocalStorage()
    url = storage.put("products/abc/photo.jpg", b"\xff\xd8\xff", "image/jpeg")

    assert url == "/static/uploads/products/abc/photo.jpg"
    assert (tmp_path / "products/abc/photo.jpg").read_bytes() == b"\xff\xd8\xff"


def test_local_delete_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_local_path", str(tmp_path), raising=False)
    storage = LocalStorage()
    storage.put("a.jpg", b"x", "image/jpeg")
    storage.delete("a.jpg")
    storage.delete("a.jpg")  # must not raise


# ══════════════════════════════════════════════════════════════════════════
# Cloudinary configuration
# ══════════════════════════════════════════════════════════════════════════


def test_cloudinary_parses_dashboard_url(monkeypatch):
    monkeypatch.setattr(settings, "storage_provider", "cloudinary", raising=False)
    monkeypatch.setattr(settings, "cloudinary_url", "cloudinary://mykey:mysecret@mycloud", raising=False)
    storage = CloudinaryStorage()
    assert storage._cloud == "mycloud"
    assert storage._key == "mykey"
    assert storage._secret == "mysecret"


def test_cloudinary_url_takes_precedence_over_discrete_settings(monkeypatch):
    monkeypatch.setattr(settings, "cloudinary_url", "cloudinary://a:b@fromurl", raising=False)
    monkeypatch.setattr(settings, "cloudinary_cloud_name", "fromfield", raising=False)
    assert CloudinaryStorage()._cloud == "fromurl"


def test_malformed_cloudinary_url_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "cloudinary_url", "cloudinary://incomplete", raising=False)
    monkeypatch.setattr(settings, "cloudinary_cloud_name", "blackhouse", raising=False)
    monkeypatch.setattr(settings, "cloudinary_api_key", "k", raising=False)
    monkeypatch.setattr(settings, "cloudinary_api_secret", "s", raising=False)
    assert CloudinaryStorage()._cloud == "blackhouse"


def test_unconfigured_cloudinary_raises_with_actionable_message(monkeypatch):
    monkeypatch.setattr(settings, "cloudinary_url", "", raising=False)
    monkeypatch.setattr(settings, "cloudinary_cloud_name", "", raising=False)
    monkeypatch.setattr(settings, "cloudinary_api_key", "", raising=False)
    monkeypatch.setattr(settings, "cloudinary_api_secret", "", raising=False)
    with pytest.raises(StorageError) as exc:
        CloudinaryStorage()
    assert "CLOUDINARY_URL" in str(exc.value)


# ══════════════════════════════════════════════════════════════════════════
# Cloudinary signature
# ══════════════════════════════════════════════════════════════════════════


def test_signature_matches_cloudinary_algorithm(cloudinary_env):
    """Sorted k=v pairs joined by &, secret appended, SHA-1 hex.

    Hand-computed so a change to the algorithm is caught rather than silently
    breaking every upload with a 401.
    """
    storage = CloudinaryStorage()
    params = {"timestamp": 1700000000, "public_id": "products/x", "folder": "products"}

    expected_input = "folder=products&public_id=products/x&timestamp=1700000000s3cr3t"
    expected = hashlib.sha1(expected_input.encode()).hexdigest()

    assert storage._sign(params) == expected


def test_signature_ignores_empty_values(cloudinary_env):
    storage = CloudinaryStorage()
    with_empties = storage._sign({"a": "1", "b": "", "c": None, "d": "2"})
    without = storage._sign({"a": "1", "d": "2"})
    assert with_empties == without, "empty params must not enter the signed string"


# ══════════════════════════════════════════════════════════════════════════
# Cloudinary upload
# ══════════════════════════════════════════════════════════════════════════


def test_upload_posts_signed_multipart_and_returns_url(cloudinary_env, monkeypatch):
    captured: dict[str, Any] = {}

    def fake_post(url, data=None, files=None, timeout=None):
        captured.update(url=url, data=data, files=files, timeout=timeout)
        return _FakeResponse(200, {"public_id": "products/abc123", "format": "jpg"})

    monkeypatch.setattr(httpx, "post", fake_post)

    url = CloudinaryStorage().put("products/abc123.jpg", b"\xff\xd8\xff", "image/jpeg")

    assert captured["url"] == "https://api.cloudinary.com/v1_1/blackhouse/image/upload"
    assert captured["data"]["api_key"] == "123456789"
    assert captured["data"]["signature"]
    assert captured["data"]["folder"] == "products"
    assert captured["data"]["overwrite"] == "true"
    # Invalidate so replacing a photo actually shows through the CDN.
    assert captured["data"]["invalidate"] == "true"
    assert isinstance(captured["timeout"], httpx.Timeout)
    assert url == "https://res.cloudinary.com/blackhouse/image/upload/products/abc123"


def test_upload_strips_the_extension_for_public_id(cloudinary_env, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, data=None, files=None, timeout=None: (
            seen.update(data=data) or _FakeResponse(200, {"public_id": data["public_id"]})
        ),
    )
    CloudinaryStorage().put("products/p1/hero.webp", b"RIFF....WEBP", "image/webp")
    assert seen["data"]["public_id"] == "products/p1/hero"


def test_upload_rejection_raises_storage_error(cloudinary_env, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(401, text="Invalid signature"))
    with pytest.raises(StorageError) as exc:
        CloudinaryStorage().put("a.jpg", b"\xff\xd8\xff", "image/jpeg")
    assert "401" in str(exc.value)


def test_network_failure_raises_storage_error(cloudinary_env, monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("dns failure")

    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(StorageError):
        CloudinaryStorage().put("a.jpg", b"\xff\xd8\xff", "image/jpeg")


def test_delete_failure_is_logged_not_raised(cloudinary_env, monkeypatch):
    """An already-unreferenced object must not fail the caller's request."""
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(420, text="rate limited"))
    CloudinaryStorage().delete("products/gone.jpg")  # must not raise


# ══════════════════════════════════════════════════════════════════════════
# Responsive delivery URLs
# ══════════════════════════════════════════════════════════════════════════


def test_url_for_adds_auto_format_and_width(cloudinary_env):
    url = CloudinaryStorage().url_for("products/hero", width=800)
    assert "f_auto" in url, "WebP/AVIF negotiation is the whole point"
    assert "q_80" in url
    assert "dpr_auto" in url
    assert "w_800" in url
    assert url.endswith("/products/hero")


def test_url_for_without_width_omits_it(cloudinary_env):
    url = CloudinaryStorage().url_for("products/hero")
    assert "w_" not in url
    assert "f_auto" in url


def test_image_url_transforms_cloudinary_urls(cloudinary_env, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(200, {}))
    stored = "https://res.cloudinary.com/blackhouse/image/upload/products/hero"
    out = image_url(stored, width=400)
    assert "/upload/f_auto,q_80,dpr_auto,w_400/products/hero" == out.split("image")[1]


def test_image_url_does_not_double_apply_transforms(cloudinary_env, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(200, {}))
    already = "https://res.cloudinary.com/blackhouse/image/upload/f_auto,q_80,dpr_auto,w_400/products/hero"
    out = image_url(already, width=400)
    assert out.count("f_auto") == 1, "transforms must not stack"


def test_image_url_leaves_local_urls_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_provider", "local", raising=False)
    monkeypatch.setattr(settings, "storage_local_path", str(tmp_path), raising=False)
    stored = "/static/uploads/products/hero.jpg"
    assert image_url(stored, width=400) == stored


def test_image_url_handles_empty():
    assert image_url("") == ""


# ══════════════════════════════════════════════════════════════════════════
# S3 URL construction (no boto3 calls — client init is stubbed)
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def s3_env(monkeypatch):
    monkeypatch.setattr(settings, "storage_provider", "s3", raising=False)
    monkeypatch.setattr(settings, "storage_bucket", "blackhouse-media", raising=False)
    monkeypatch.setattr(settings, "storage_region", "ap-south-1", raising=False)
    monkeypatch.setattr(settings, "storage_access_key", "AKIA", raising=False)
    monkeypatch.setattr(settings, "storage_secret_key", "secret", raising=False)
    monkeypatch.setattr(settings, "storage_cdn_base_url", "", raising=False)
    monkeypatch.setattr(settings, "storage_endpoint_url", "", raising=False)

    class _FakeBoto3:
        @staticmethod
        def client(*a, **k):
            return object()

    import sys

    monkeypatch.setitem(sys.modules, "boto3", _FakeBoto3)
    yield


def test_s3_requires_a_bucket(monkeypatch):
    monkeypatch.setattr(settings, "storage_bucket", "", raising=False)
    import sys

    class _FakeBoto3:
        @staticmethod
        def client(*a, **k):
            return object()

    monkeypatch.setitem(sys.modules, "boto3", _FakeBoto3)
    with pytest.raises(StorageError) as exc:
        storage_service.S3Storage()
    assert "STORAGE_BUCKET" in str(exc.value)


def test_s3_public_url_uses_bucket_endpoint(s3_env):
    storage = storage_service.S3Storage()
    assert storage.public_url("a/b.jpg") == ("https://blackhouse-media.s3.ap-south-1.amazonaws.com/a/b.jpg")


def test_s3_public_url_prefers_cdn(s3_env, monkeypatch):
    monkeypatch.setattr(settings, "storage_cdn_base_url", "https://cdn.blackhouse.example/", raising=False)
    storage = storage_service.S3Storage()
    assert storage.public_url("a/b.jpg") == "https://cdn.blackhouse.example/a/b.jpg"


def test_s3_has_no_image_transforms(s3_env):
    """Plain S3 serves bytes as stored — url_for must not invent transforms."""
    storage = storage_service.S3Storage()
    assert storage.url_for("a/b.jpg", width=400) == storage.public_url("a/b.jpg")


# ══════════════════════════════════════════════════════════════════════════
# Filename sanitising
# ══════════════════════════════════════════════════════════════════════════


def test_safe_filename_strips_path_traversal():
    out = safe_filename("../../etc/passwd")
    assert "/" not in out
    assert ".." not in out


def test_safe_filename_strips_shell_metacharacters():
    out = safe_filename("photo;rm -rf.png")
    assert ";" not in out and " " not in out
    assert out.endswith(".png")


def test_safe_filename_reduces_a_path_to_its_basename():
    """A slash inside the "filename" must not survive into the storage key."""
    out = safe_filename("photo;rm -rf /.png")
    assert "/" not in out
    assert ";" not in out


def test_safe_filename_rejects_windows_traversal():
    out = safe_filename("..\\..\\windows\\system32\\config.png")
    assert "\\" not in out and ".." not in out and "/" not in out
    assert out.endswith(".png")


def test_safe_filename_discards_a_suffix_that_is_not_an_extension():
    """Regression: '.png' as a whole name used to yield '.png-<hex>.jpg'."""
    out = safe_filename(".png")
    assert not out.startswith(".")
    assert re.fullmatch(r"png-[0-9a-f]{8}\.jpg", out)


def test_safe_filename_rejects_an_absurd_suffix():
    out = safe_filename("photo." + "x" * 40)
    assert out.endswith(".jpg"), "over-long suffix must fall back, not be trusted"


def test_safe_filename_caps_length_and_is_unique():
    a = safe_filename("x" * 500 + ".jpg")
    b = safe_filename("x" * 500 + ".jpg")
    assert len(a) < 80
    assert a != b, "collision-free suffix required"


def test_safe_filename_defaults_when_stem_is_empty():
    assert safe_filename("!!!.jpg").startswith("image-")
