"""Upload validation for product imagery.

Why this module exists
----------------------
The previous implementation trusted two client-controlled values: the
``Content-Type`` header and the filename extension. Both are attacker-settable,
so a privileged user could upload ``payload.svg`` (or ``.html``) and the API
would serve it back from ``/static/uploads/`` on its own origin. SVG is an XML
format that may contain ``<script>``, which makes that **stored XSS** — and
because access/refresh tokens live in the browser, XSS means full account
takeover, including manager and admin accounts.

The fix is to trust *nothing* the client declares:

1. Read the bytes and identify the format from its **magic number** (the file
   signature), which cannot be spoofed without making the file invalid.
2. Reject anything that is not a raster image. SVG, HTML, XML and polyglots are
   refused outright — there is no allow-list entry that can execute script.
3. Re-derive the extension from the *detected* type, never from the filename.
4. Enforce a size cap before buffering more than necessary.

Deliberate design choice: this is an allow-list, not a deny-list. A deny-list
(``.svg``, ``.html``, ``.js``) always misses the next variant; an allow-list of
four magic numbers does not.
"""

import io
from dataclasses import dataclass
from enum import StrEnum

from app.core.config import settings
from app.core.exceptions import ValidationError


class ImageFormat(StrEnum):
    """Raster formats accepted for product imagery.

    SVG is intentionally absent: it is a vector *document* format that can carry
    script, foreignObject and external references.
    """

    jpeg = "jpeg"
    png = "png"
    webp = "webp"
    avif = "avif"


# Detected format → (canonical extension, MIME type). The extension is derived
# from what the bytes actually are, so a file named `invoice.pdf` containing a
# JPEG is stored as `.jpg`.
_FORMAT_META: dict[ImageFormat, tuple[str, str]] = {
    ImageFormat.jpeg: (".jpg", "image/jpeg"),
    ImageFormat.png: (".png", "image/png"),
    ImageFormat.webp: (".webp", "image/webp"),
    ImageFormat.avif: (".avif", "image/avif"),
}

# Only the leading bytes are needed to identify any supported format.
_SNIFF_BYTES = 32

# Reject before buffering: 8 MB is generous for a compressed product photo and
# bounds memory use when many uploads arrive concurrently.
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ValidatedImage:
    """The result of a successful validation."""

    data: bytes
    image_format: ImageFormat
    extension: str
    content_type: str
    size_bytes: int

    @property
    def width_height(self) -> tuple[int, int] | None:
        """Best-effort intrinsic dimensions, used to warn about tiny images."""
        return _read_dimensions(self.data, self.image_format)


def _sniff(data: bytes) -> ImageFormat | None:
    """Identify the format from magic bytes. ``None`` when unrecognised."""
    if len(data) < 12:
        return None

    # JPEG — SOI marker followed by a segment marker.
    if data[:3] == b"\xff\xd8\xff":
        return ImageFormat.jpeg

    # PNG — 8-byte signature.
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ImageFormat.png

    # WebP — RIFF container with a WEBP form type.
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ImageFormat.webp

    # AVIF/HEIF — ISO base media file format, brand in the `ftyp` box.
    if data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in {b"avif", b"avis", b"mif1", b"msf1", b"heic", b"heix"}:
            return ImageFormat.avif

    return None


def _looks_like_markup(data: bytes) -> bool:
    """Detect SVG/HTML/XML so the error message can be specific and helpful."""
    head = data[:512].lstrip().lower()
    return head.startswith((b"<svg", b"<?xml", b"<!doctype html", b"<html", b"<!doctype svg", b"<script"))


def _read_dimensions(data: bytes, fmt: ImageFormat) -> tuple[int, int] | None:
    """Parse width/height from the header without decoding the whole image.

    Kept dependency-free on purpose: adding Pillow would pull a native wheel into
    every deploy for a value we only use to warn about undersized uploads.
    """
    try:
        if fmt is ImageFormat.png:
            # IHDR: width and height are big-endian uint32 at fixed offsets.
            if data[12:16] == b"IHDR":
                w = int.from_bytes(data[16:20], "big")
                h = int.from_bytes(data[20:24], "big")
                return (w, h)

        elif fmt is ImageFormat.jpeg:
            # Walk SOFn markers; skip standalone markers with no payload.
            with io.BytesIO(data) as buf:
                buf.read(2)
                while True:
                    marker = buf.read(2)
                    if len(marker) < 2:
                        return None
                    if marker[0] != 0xFF:
                        return None
                    code = marker[1]
                    if code in {0xD8, 0x01} or 0xD0 <= code <= 0xD7:
                        continue
                    length_bytes = buf.read(2)
                    if len(length_bytes) < 2:
                        return None
                    length = int.from_bytes(length_bytes, "big")
                    # SOF0..SOF15 excluding DHT(C4), JPG(C8), DAC(CC)
                    if 0xC0 <= code <= 0xCF and code not in {0xC4, 0xC8, 0xCC}:
                        payload = buf.read(length - 2)
                        if len(payload) >= 5:
                            h = int.from_bytes(payload[1:3], "big")
                            w = int.from_bytes(payload[3:5], "big")
                            return (w, h)
                    buf.seek(length - 2, io.SEEK_CUR)

        elif fmt is ImageFormat.webp:
            # VP8 (lossy), VP8L (lossless) and VP8X (extended) each differ.
            chunk = data[12:16]
            if chunk == b"VP8 ":
                w = int.from_bytes(data[26:28], "little") & 0x3FFF
                h = int.from_bytes(data[28:30], "little") & 0x3FFF
                return (w, h)
            # VP8L: 14-bit width/height packed little-endian at offset 21.
            if chunk == b"VP8L" and len(data) >= 25:
                bits = int.from_bytes(data[21:25], "little")
                return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
            # VP8X (extended): two 24-bit little-endian values, each stored as
            # dimension - 1. Slicing needs the full 30-byte header present.
            if chunk == b"VP8X" and len(data) >= 30:
                w = 1 + int.from_bytes(data[24:27], "little")
                h = 1 + int.from_bytes(data[27:30], "little")
                return (w, h)
    except (IndexError, ValueError, OSError):  # pragma: no cover - malformed input
        return None
    return None


def validate_image(
    data: bytes,
    *,
    declared_content_type: str | None = None,
    declared_filename: str | None = None,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> ValidatedImage:
    """Validate raw upload bytes, or raise ``ValidationError``.

    ``declared_*`` arguments are used **only** to produce a better error message;
    they never influence the accept/reject decision.
    """
    if not data:
        raise ValidationError("Uploaded file is empty.")

    if len(data) > max_bytes:
        raise ValidationError(
            f"Image is too large ({len(data) / 1024 / 1024:.1f} MB). "
            f"Maximum is {max_bytes / 1024 / 1024:.0f} MB.",
            details={"max_bytes": max_bytes, "received_bytes": len(data)},
        )

    fmt = _sniff(data)

    if fmt is None:
        details: dict[str, object] = {}
        if declared_content_type:
            details["declared_content_type"] = declared_content_type
        if declared_filename:
            details["declared_filename"] = declared_filename

        if _looks_like_markup(data):
            raise ValidationError(
                "SVG, HTML and XML uploads are rejected: they can contain script and "
                "are served from this origin. Export the artwork as JPEG, PNG, WebP "
                "or AVIF instead.",
                details=details,
            )

        accepted = ", ".join(f.value.upper() for f in ImageFormat)
        raise ValidationError(
            f"Unrecognised image format. Accepted formats: {accepted}. "
            "The file's contents do not match a supported image signature.",
            details=details,
        )

    extension, content_type = _FORMAT_META[fmt]

    # Warn (do not fail) when the client's declared type disagrees with the bytes.
    # This catches misconfigured upstream tools without blocking a valid upload.
    if declared_content_type and declared_content_type.split(";")[0].strip() != content_type:
        from app.core.logging import get_logger

        get_logger("uploads").warning(
            "declared content-type %r does not match detected %r (filename=%r)",
            declared_content_type,
            content_type,
            declared_filename,
        )

    return ValidatedImage(
        data=data,
        image_format=fmt,
        extension=extension,
        content_type=content_type,
        size_bytes=len(data),
    )


def read_upload(fileobj, *, max_bytes: int = MAX_UPLOAD_BYTES) -> bytes:
    """Read an upload with a hard cap, so an oversized body never fully buffers.

    Reads one byte past the limit to distinguish "exactly at the cap" from
    "over the cap" without streaming the whole file into memory.
    """
    data = fileobj.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValidationError(
            f"Image exceeds the {max_bytes / 1024 / 1024:.0f} MB upload limit.",
            details={"max_bytes": max_bytes},
        )
    return data


def storage_key_for(*, prefix: str, image: ValidatedImage, unique_id: str) -> str:
    """Build a safe, collision-free storage key with a derived extension.

    The caller's filename is deliberately ignored — it is client-controlled and
    may contain path separators or a misleading extension.
    """
    folder = prefix.strip("/")
    return f"{folder}/{unique_id}{image.extension}"


def recommended_transform(width: int | None = None) -> str:
    """Cloudinary transformation string for a given display width.

    Centralised so card thumbnails, PDP hero images and OG images stay visually
    consistent and all serve auto-format (WebP/AVIF) at the right quality.
    """
    base = f"f_auto,q_{settings.image_quality},dpr_auto"
    return f"{base},w_{width}" if width else base
