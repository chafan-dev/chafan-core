"""Server-side image sanitization: decode with Pillow, re-encode with no metadata.

The PWA strips EXIF with ``piexifjs`` and caps at 500px, but the API is public:
against a modified or third-party client that pass does nothing. GPS EXIF
leaking a home address is silent and irreversible, so the guarantee must live
on the server.

``sanitize`` decodes the bytes and re-encodes them with no metadata, returning
the clean bytes and the real content type. Three consequences to note:

  * The content address is the hash of the *sanitized* bytes, so two copies of
    the same photo with different EXIF dedupe to one object.
  * A successful decode replaces magic-byte sniffing: anything Pillow rejects
    becomes a 415.
  * Animated GIFs need ``save_all=True`` or they flatten to one frame.
"""

from __future__ import annotations

import io
from typing import Tuple

from PIL import Image

# Decoding hostile input is its own attack surface: 5 MB of compressed data can
# expand a long way. ~50M pixels bounds the decompression.
MAX_IMAGE_PIXELS = 50_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

# Clamp still images to this max dimension, well above the PWA's 500px so
# nothing it sends is touched, but bounding how fast the storage grant burns.
MAX_DIMENSION = 2000

_SUPPORTED_FORMATS = ("JPEG", "PNG", "GIF", "WEBP")


class UnsupportedImage(ValueError):
    """Raised when the bytes are not a supported, decodable image."""


def sanitize(raw: bytes) -> Tuple[bytes, str]:
    try:
        img = Image.open(io.BytesIO(raw))
        fmt = (img.format or "").upper()
        if fmt not in _SUPPORTED_FORMATS:
            raise UnsupportedImage(f"unsupported image format: {fmt or '(none)'}")
        if fmt == "GIF":
            return _sanitize_gif(img)
        img.load()
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
        img = _prepare_for_save(img, fmt)
    except UnsupportedImage:
        raise
    except Exception as exc:  # decode failures, decompression bombs, ...
        raise UnsupportedImage(str(exc)) from exc

    out = io.BytesIO()
    try:
        if fmt == "JPEG":
            img.save(out, format="JPEG", optimize=True)
            return out.getvalue(), "image/jpeg"
        if fmt == "PNG":
            img.save(out, format="PNG", optimize=True)
            return out.getvalue(), "image/png"
        img.save(out, format="WEBP")
        return out.getvalue(), "image/webp"
    except Exception as exc:
        raise UnsupportedImage(str(exc)) from exc


def _prepare_for_save(img: Image.Image, fmt: str) -> Image.Image:
    if fmt != "JPEG":
        return img
    if img.mode in ("RGB", "L"):
        return img
    # JPEG has no alpha channel; composite onto white rather than dropping it
    # onto black (Pillow's default conversion for RGBA).
    rgba = img.convert("RGBA")
    background = Image.new("RGB", rgba.size, (255, 255, 255))
    background.paste(rgba, mask=rgba.split()[-1])
    return background


def _sanitize_gif(img: Image.Image) -> Tuple[bytes, str]:
    # save_all preserves the animation frames; without it a GIF avatar flattens
    # to a single frame. No dimension clamp here: resizing animated GIFs is out
    # of scope and the PWA sends raw GIF avatars (its only uncapped path).
    out = io.BytesIO()
    img.save(out, format="GIF", save_all=True, loop=img.info.get("loop", 0))
    return out.getvalue(), "image/gif"
