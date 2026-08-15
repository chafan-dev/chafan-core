"""s15 — image upload: the spec, now enforced.

This scenario is the executable spec for ``POST /api/v1/upload/images/``. It was
written before the endpoint existed and reported XFAIL on every point the
backend did not yet satisfy; the endpoint has since landed, so each point is now
a hard assertion and a regression fails the suite.

Spec points (see the image-upload proposal):

  1. Anonymous uploads are refused: no token → 401/403.
  2. ``purpose="figure"`` is gated on karma ≥ 100 (``rules.MIN_KARMA_UPLOAD_IMAGE``);
     ``purpose="avatar"`` is exempt and succeeds for a low-karma account.
  3. ``purpose`` is a closed set: anything else → 422, never a third class of
     upload that is neither gated nor detected.
  4. A new upload costs ``rules.UPLOAD_IMAGE_COST`` = 2 coins, and the response
     URL is content-addressed — ``{base}/{sha}.{ext}`` with a 64-hex sha — never
     a placeholder.
  5. Re-uploading identical bytes is free (no extra coin) and returns the same
     URL.
  6. Non-image bytes are refused with 415.
  7. Files over the size cap (``common.MAX_UPLOAD_BYTES`` = 5 MB) are refused.
  8. The legacy ``POST /upload/vditor/`` endpoint is gone → 404.

Every check that uploads a real image builds its own bytes with
``_unique_png()``. Sharing one fixture between checks is what made the coin
assertion wrong before: the server deduplicates on the sha of the *sanitized*
bytes, so a "new" upload of bytes another check had already sent is correctly
free, and the "costs 2 coins" point failed against a backend that was right.
"""
from __future__ import annotations

import random
import re
import struct
import zlib

from client import ApiClient, ApiError, note, ok

TAG = "s15_upload"

# rules.MIN_KARMA_UPLOAD_IMAGE / rules.UPLOAD_IMAGE_COST, duplicated here
# because the smoke suite does not import app code.
_KARMA_GATE = 100
_COIN_COST = 2

_SHA_RE = re.compile(r"[0-9a-f]{64}")

_UPLOAD_PATH = "/api/v1/upload/images/"


def _png(pixels: bytes) -> bytes:
    """A 4x1 truecolour PNG of ``pixels``, built with the standard library."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 4, 1, 8, 2, 0, 0, 0)  # 4x1, 8-bit, truecolour
    idat = zlib.compress(b"\x00" + pixels)  # one scanline, filter type 0
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )


def _unique_png() -> bytes:
    """Distinct bytes on every call, so "this upload is new" is actually true.

    The uniqueness has to come from the pixels: the server strips metadata
    before hashing, so two images differing only in a comment would dedupe to
    one object. Twelve random bytes also keeps a re-run against an already
    seeded database honest.
    """
    return _png(bytes(random.randrange(256) for _ in range(12)))


def _content_addressed(url) -> bool:
    return bool(url) and "picsum.photos" not in url and bool(_SHA_RE.search(url))


def _upload_status(client: ApiClient, path: str = _UPLOAD_PATH, **kwargs) -> int:
    """Upload and return the status: 200 on success, the error's otherwise.

    Returning the status rather than a bool keeps the "expected X, got Y" that
    the XFAIL notes used to print, now in the assertion message.
    """
    try:
        client.upload(path, **kwargs)
    except ApiError as e:
        return e.status_code
    return 200


def _check_anon_upload_refused(anon: ApiClient) -> None:
    status = _upload_status(
        anon,
        file_bytes=_unique_png(),
        filename="a.png",
        content_type="image/png",
        purpose="figure",
    )
    assert status in (401, 403), f"anon upload: expected 401/403, got {status}"
    ok(TAG, "anon upload → 401/403")


def _accounts_on_opposite_sides(me_a: dict, me_b: dict) -> bool:
    """A must be ≥ the karma gate and B below it, or this scenario can't run.

    A precondition of the seeded dataset rather than an assertion about the
    endpoint, so it skips (like s14's site-creation preconditions) instead of
    failing.
    """
    if me_a.get("karma", 0) < _KARMA_GATE or me_b.get("karma", 0) >= _KARMA_GATE:
        note(
            TAG,
            "accounts on opposite sides of the karma gate",
            "SKIP",
            f"karma A={me_a.get('karma')} B={me_b.get('karma')}",
        )
        return False
    return True


def _check_low_karma_figure_refused(b: ApiClient) -> None:
    status = _upload_status(
        b,
        file_bytes=_unique_png(),
        filename="b.png",
        content_type="image/png",
        purpose="figure",
    )
    assert status == 403, f"low-karma figure: expected 403, got {status}"
    ok(TAG, "low-karma figure → 403")


def _check_low_karma_avatar_exempt(b: ApiClient) -> None:
    resp = b.upload(
        _UPLOAD_PATH,
        file_bytes=_unique_png(),
        filename="b-avatar.png",
        content_type="image/png",
        purpose="avatar",
    )
    url = resp.get("url", "")
    assert _content_addressed(url), f"got {url!r}, expected a content-addressed URL"
    ok(TAG, "low-karma avatar → 200 (exempt)", f"url={url}")


def _check_unknown_purpose_refused(b: ApiClient) -> None:
    """An unknown purpose is refused rather than becoming a third class.

    Sent from the low-karma account: if the server accepted it, that account
    would have uploaded a figure without the karma the gate requires, and the
    read-time avatar-misuse detection would never see it either.
    """
    status = _upload_status(
        b,
        file_bytes=_unique_png(),
        filename="b-other.png",
        content_type="image/png",
        purpose="banana",
    )
    assert status == 422, f"unknown purpose: expected 422, got {status}"
    ok(TAG, "unknown purpose → 422")


def _check_new_figure(a: ApiClient, me_a: dict):
    """New figure must return a content-addressed URL and cost 2 coins.

    Returns (data, url, coins_after) for the deduplicate check to reuse.
    """
    coins_before = me_a.get("remaining_coins", 0)
    data = _unique_png()
    resp = a.upload(
        _UPLOAD_PATH,
        file_bytes=data,
        filename="a.png",
        content_type="image/png",
        purpose="figure",
    )
    url = resp.get("url", "")
    assert _content_addressed(url), f"got {url!r}, expected a content-addressed URL"

    coins_after = a.get("/api/v1/me")["remaining_coins"]
    charged = coins_before - coins_after
    assert charged == _COIN_COST, f"charged {charged} coins, expected {_COIN_COST}"
    ok(TAG, "new figure → content-addressed URL, costs 2 coins", f"url={url}")
    return data, url, coins_after


def _check_identical_bytes_free(
    a: ApiClient, data: bytes, url: str, coins_after: int
) -> None:
    resp = a.upload(
        _UPLOAD_PATH,
        file_bytes=data,
        filename="a-again.png",
        content_type="image/png",
        purpose="figure",
    )
    again = resp.get("url", "")
    assert again == url, f"got {again!r}, expected the same URL {url!r}"
    coins_now = a.get("/api/v1/me")["remaining_coins"]
    assert coins_now == coins_after, (
        f"re-upload charged {coins_after - coins_now} coins, expected 0"
    )
    ok(TAG, "identical bytes are free and deduplicate", f"url={again}")


def _check_non_image_refused(a: ApiClient) -> None:
    status = _upload_status(
        a,
        file_bytes=b"this is definitely not an image",
        filename="fake.png",
        content_type="image/png",
        purpose="figure",
    )
    assert status == 415, f"non-image bytes: expected 415, got {status}"
    ok(TAG, "non-image bytes → 415")


def _check_oversize_refused(a: ApiClient) -> None:
    status = _upload_status(
        a,
        file_bytes=b"\x00" * (5_000_000 + 1),
        filename="big.png",
        content_type="image/png",
        purpose="figure",
    )
    assert status in (413, 422), f"oversize file: expected 413/422, got {status}"
    ok(TAG, "oversize file → 413/422")


def _check_vditor_removed(a: ApiClient) -> None:
    status = _upload_status(
        a,
        "/api/v1/upload/vditor/",
        file_bytes=_unique_png(),
        filename="a.png",
        content_type="image/png",
    )
    assert status == 404, f"vditor endpoint: expected 404, got {status}"
    ok(TAG, "vditor endpoint removed → 404")


def run(state: dict) -> None:
    a = state["a"]
    b = state["b"]
    cfg = state["cfg"]
    anon = ApiClient(cfg["api_base"], "anon")

    _check_anon_upload_refused(anon)

    me_a = a.get("/api/v1/me")
    me_b = b.get("/api/v1/me")
    if not _accounts_on_opposite_sides(me_a, me_b):
        return

    _check_low_karma_figure_refused(b)
    _check_low_karma_avatar_exempt(b)
    _check_unknown_purpose_refused(b)
    data, url, coins_after = _check_new_figure(a, me_a)
    _check_identical_bytes_free(a, data, url, coins_after)
    _check_non_image_refused(a)
    _check_oversize_refused(a)
    _check_vditor_removed(a)


if __name__ == "__main__":
    from scenarios import bootstrap

    run(bootstrap.build_state())
