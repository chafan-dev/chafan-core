"""Unit tests for server-side image sanitization.

The inputs are generated with Pillow itself, so there are no binary fixtures:
every case is a tiny deterministic image built in-memory.
"""

import hashlib
import io

import pytest
from PIL import Image

from chafan_core.app.image_sanitize import (
    MAX_DIMENSION,
    UnsupportedImage,
    sanitize,
)


def _png(size=(1, 1), color=(255, 0, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg(description, *, gps=False) -> bytes:
    img = Image.new("RGB", (20, 20), (10, 20, 30))
    exif = Image.Exif()
    exif[0x010E] = description  # ImageDescription
    if gps:
        gps_ifd = exif.get_ifd(0x8825)
        gps_ifd[1] = "N"
        gps_ifd[2] = (38.0, 53.0, 0.0)
        gps_ifd[3] = "W"
        gps_ifd[4] = (77.0, 2.0, 0.0)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def _animated_gif() -> bytes:
    f1 = Image.new("RGB", (10, 10), (255, 0, 0))
    f2 = Image.new("RGB", (10, 10), (0, 255, 0))
    buf = io.BytesIO()
    f1.save(buf, format="GIF", save_all=True, append_images=[f2], loop=0, duration=100)
    return buf.getvalue()


def test_sanitize_png() -> None:
    clean, content_type = sanitize(_png())
    assert content_type == "image/png"
    assert Image.open(io.BytesIO(clean)).format == "PNG"


def test_sanitize_strips_exif() -> None:
    raw = _jpeg("GPS location of my house", gps=True)
    assert Image.open(io.BytesIO(raw)).getexif(), "fixture must carry EXIF"

    clean, content_type = sanitize(raw)
    assert content_type == "image/jpeg"
    assert Image.open(io.BytesIO(clean)).getexif() == {}, "stored bytes carry EXIF"


def test_sanitize_preserves_animated_gif() -> None:
    clean, content_type = sanitize(_animated_gif())
    assert content_type == "image/gif"
    assert Image.open(io.BytesIO(clean)).n_frames > 1, "GIF flattened to one frame"


def test_sanitize_rejects_non_image() -> None:
    with pytest.raises(UnsupportedImage):
        sanitize(b"this is definitely not an image")


def test_sanitize_rejects_unsupported_format() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (1, 2, 3)).save(buf, format="BMP")
    with pytest.raises(UnsupportedImage):
        sanitize(buf.getvalue())


def test_sanitize_clamps_large_image() -> None:
    clean, content_type = sanitize(_png(size=(4000, 4000)))
    assert content_type == "image/png"
    width, height = Image.open(io.BytesIO(clean)).size
    assert max(width, height) <= MAX_DIMENSION


def test_sanitize_webp() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (0, 0, 255)).save(buf, format="WEBP")
    clean, content_type = sanitize(buf.getvalue())
    assert content_type == "image/webp"
    assert Image.open(io.BytesIO(clean)).format == "WEBP"


def test_same_pixels_different_exif_sanitize_identically() -> None:
    clean_a, type_a = sanitize(_jpeg("first copy"))
    clean_b, type_b = sanitize(_jpeg("second copy"))
    assert type_a == type_b == "image/jpeg"
    assert clean_a == clean_b, "different EXIF must not change the sanitized bytes"
    assert hashlib.sha256(clean_a).hexdigest() == hashlib.sha256(clean_b).hexdigest()
