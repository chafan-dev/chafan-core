"""s15 — image upload: the spec (KNOWN-FAILING until the endpoint is built).

This scenario is the executable spec for ``POST /api/v1/upload/images/``. It is
expected to print XFAIL (known failure) against a backend that has not yet
implemented the endpoint, and to flip to OK once the implementation lands.
Review the *steps*, not the pass/fail: each step is a statement about what the
endpoint must do, with "expected … got …" on the XFAIL line.

Spec points (see the image-upload proposal):

  1. Anonymous uploads are refused: no token → 401/403.
  2. ``purpose="figure"`` is gated on karma ≥ 100 (``rules.MIN_KARMA_UPLOAD_IMAGE``);
     ``purpose="avatar"`` is exempt and succeeds for a low-karma account.
  3. A new upload costs ``rules.UPLOAD_IMAGE_COST`` = 2 coins, and the response
     URL is content-addressed — ``{base}/{sha}.{ext}`` with a 64-hex sha — never
     a placeholder.
  4. Re-uploading identical bytes is free (no extra coin) and returns the same
     URL.
  5. Non-image bytes are refused with 415.
  6. Files over the size cap (``common.MAX_UPLOAD_BYTES`` = 5 MB) are refused.
  7. The legacy ``POST /upload/vditor/`` endpoint is gone → 404.

The object-store-dependent steps are exercised against whatever store the
deployment configures via ``UPLOADS_S3_*`` (MinIO in CI); the deduplicate step
is skipped when the endpoint is not live, since the legacy placeholder endpoint
returns the same URL for any bytes and charges nothing, which would be a false
pass.
"""
from __future__ import annotations

import base64
import re

from client import ApiClient, ApiError, note, ok

TAG = "s15_upload"

# A valid 1x1 PNG, so the server-side sanitizer accepts it once the endpoint
# lands (and the legacy endpoint accepts anything).
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)

# rules.MIN_KARMA_UPLOAD_IMAGE / rules.UPLOAD_IMAGE_COST, duplicated here
# because the smoke suite does not import app code.
_KARMA_GATE = 100
_COIN_COST = 2

_SHA_RE = re.compile(r"[0-9a-f]{64}")


def _content_addressed(url) -> bool:
    return bool(url) and "picsum.photos" not in url and bool(_SHA_RE.search(url))


def _describe(resp) -> str:
    """A short "got X, expected a content-addressed URL" for an XFAIL note."""
    if resp is None:
        return "request was refused, expected a content-addressed URL"
    url = resp.get("url", "") if isinstance(resp, dict) else resp
    return f"got {url!r}, expected a content-addressed URL"


def _upload_ok(client: ApiClient, **kwargs):
    """Upload and return the response body, or None if the server refused."""
    try:
        return client.upload("/api/v1/upload/images/", **kwargs)
    except ApiError:
        return None


def _upload_refused(client: ApiClient, statuses, **kwargs) -> bool:
    """Upload and return True if it was refused with one of `statuses`."""
    try:
        client.upload("/api/v1/upload/images/", **kwargs)
    except ApiError as e:
        return e.status_code in statuses
    return False


def _check_anon_upload_refused(anon: ApiClient) -> None:
    if _upload_refused(
        anon,
        (401, 403),
        file_bytes=_PNG,
        filename="a.png",
        content_type="image/png",
        purpose="figure",
    ):
        ok(TAG, "anon upload → 401/403")
    else:
        note(TAG, "anon upload → 401/403", "XFAIL", "anonymous upload was accepted")


def _accounts_on_opposite_sides(me_a: dict, me_b: dict) -> bool:
    """A must be ≥ the karma gate and B below it, or this scenario can't run."""
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
    if _upload_refused(
        b,
        (403,),
        file_bytes=_PNG,
        filename="b.png",
        content_type="image/png",
        purpose="figure",
    ):
        ok(TAG, "low-karma figure → 403")
    else:
        note(TAG, "low-karma figure → 403", "XFAIL", "low-karma figure was accepted")


def _check_low_karma_avatar_exempt(b: ApiClient) -> None:
    resp = _upload_ok(
        b,
        file_bytes=_PNG,
        filename="b-avatar.png",
        content_type="image/png",
        purpose="avatar",
    )
    url = (resp or {}).get("url", "") if isinstance(resp, dict) else ""
    if _content_addressed(url):
        ok(TAG, "low-karma avatar → 200 (exempt)", f"url={url}")
    else:
        note(TAG, "low-karma avatar → 200 (exempt)", "XFAIL", _describe(resp))


def _check_new_figure(a: ApiClient, me_a: dict):
    """New figure must return a content-addressed URL and cost 2 coins.

    Returns (live, url, coins_after): ``live`` is True when the endpoint is up
    and storing real objects (a content-addressed URL came back), which is what
    gates the deduplicate step.
    """
    coins_before = me_a.get("remaining_coins", 0)
    resp = _upload_ok(
        a,
        file_bytes=_PNG,
        filename="a.png",
        content_type="image/png",
        purpose="figure",
    )
    url = (resp or {}).get("url", "") if isinstance(resp, dict) else ""
    if not _content_addressed(url):
        note(TAG, "new figure → content-addressed URL, costs 2 coins", "XFAIL", _describe(resp))
        return False, "", 0

    coins_after = a.get("/api/v1/me")["remaining_coins"]
    if coins_before - coins_after == _COIN_COST:
        ok(TAG, "new figure → content-addressed URL, costs 2 coins", f"url={url}")
    else:
        note(
            TAG,
            "new figure → content-addressed URL, costs 2 coins",
            "XFAIL",
            f"charged {coins_before - coins_after} coins, expected {_COIN_COST}",
        )
    return True, url, coins_after


def _check_identical_bytes_free(a: ApiClient, live: bool, url: str, coins_after: int) -> None:
    if not live:
        note(TAG, "identical bytes are free and deduplicate", "SKIP", "endpoint not live")
        return
    resp = _upload_ok(
        a,
        file_bytes=_PNG,
        filename="a-again.png",
        content_type="image/png",
        purpose="figure",
    )
    again = (resp or {}).get("url", "") if isinstance(resp, dict) else ""
    coins_now = a.get("/api/v1/me")["remaining_coins"]
    if again == url and coins_now == coins_after:
        ok(TAG, "identical bytes are free and deduplicate", f"url={again}")
    else:
        note(
            TAG,
            "identical bytes are free and deduplicate",
            "XFAIL",
            f"url={again!r}, coins {coins_after} → {coins_now}",
        )


def _check_non_image_refused(a: ApiClient) -> None:
    if _upload_refused(
        a,
        (415,),
        file_bytes=b"this is definitely not an image",
        filename="fake.png",
        content_type="image/png",
        purpose="figure",
    ):
        ok(TAG, "non-image bytes → 415")
    else:
        note(TAG, "non-image bytes → 415", "XFAIL", "non-image bytes were accepted")


def _check_oversize_refused(a: ApiClient) -> None:
    if _upload_refused(
        a,
        (413, 422),
        file_bytes=b"\x00" * (5_000_000 + 1),
        filename="big.png",
        content_type="image/png",
        purpose="figure",
    ):
        ok(TAG, "oversize file → 413/422")
    else:
        note(TAG, "oversize file → 413/422", "XFAIL", "oversize file was accepted")


def _check_vditor_removed(a: ApiClient) -> None:
    try:
        a.upload(
            "/api/v1/upload/vditor/",
            file_bytes=_PNG,
            filename="a.png",
            content_type="image/png",
        )
    except ApiError as e:
        if e.status_code == 404:
            ok(TAG, "vditor endpoint removed → 404")
        else:
            note(TAG, "vditor endpoint removed → 404", "XFAIL", f"expected 404, got {e.status_code}")
    else:
        note(TAG, "vditor endpoint removed → 404", "XFAIL", "endpoint still exists")


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
    live, url, coins_after = _check_new_figure(a, me_a)
    _check_identical_bytes_free(a, live, url, coins_after)
    _check_non_image_refused(a)
    _check_oversize_refused(a)
    _check_vditor_removed(a)


if __name__ == "__main__":
    from scenarios import bootstrap

    run(bootstrap.build_state())
