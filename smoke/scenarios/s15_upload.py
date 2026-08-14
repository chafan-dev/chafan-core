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

The object-store-dependent steps (3-6) are exercised against whatever object
store the deployment configures via ``UPLOADS_S3_*``; in the CI bootstrap run
that is MinIO. They are skipped rather than falsely passed when the store is
not reachable.
"""
from __future__ import annotations

import base64
import re
import uuid as uuidlib

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


class _SpecViolation(Exception):
    """The current backend does not satisfy the spec yet."""


def _spec(label: str, check) -> None:
    try:
        check()
    except _SpecViolation as e:
        note(TAG, label, "XFAIL", str(e))
    except ApiError as e:
        note(TAG, label, "XFAIL", f"unexpected HTTP {e.status_code}")
    else:
        ok(TAG, label)


def _upload_ok(client: ApiClient, **kwargs):
    try:
        return client.upload("/api/v1/upload/images/", **kwargs)
    except ApiError as e:
        raise _SpecViolation(f"expected success, got HTTP {e.status_code}") from None


def _expect_refused(client: ApiClient, statuses, **kwargs) -> None:
    try:
        client.upload("/api/v1/upload/images/", **kwargs)
    except ApiError as e:
        if e.status_code in statuses:
            return
        raise _SpecViolation(
            f"expected HTTP {sorted(statuses)}, got {e.status_code}"
        ) from None
    raise _SpecViolation(f"expected HTTP {sorted(statuses)}, but it succeeded")


def _is_content_addressed(url) -> bool:
    return (
        bool(url)
        and "picsum.photos" not in url
        and bool(_SHA_RE.search(url))
    )


def run(state: dict) -> None:
    a = state["a"]
    b = state["b"]
    cfg = state["cfg"]

    anon = ApiClient(cfg["api_base"], "anon")

    # ---- 1. anonymous upload is refused ---------------------------------
    _spec(
        "anon upload → 401/403",
        lambda: _expect_refused(
            anon,
            (401, 403),
            file_bytes=_PNG,
            filename="a.png",
            content_type="image/png",
            purpose="figure",
        ),
    )

    # ---- guard: A and B must sit on opposite sides of the karma gate -----
    me_a = a.get("/api/v1/me")
    me_b = b.get("/api/v1/me")
    if me_a.get("karma", 0) < _KARMA_GATE or me_b.get("karma", 0) >= _KARMA_GATE:
        note(
            TAG,
            "accounts on opposite sides of the karma gate",
            "SKIP",
            f"karma A={me_a.get('karma')} B={me_b.get('karma')}",
        )
        return

    # ---- 2. low-karma figure is refused ---------------------------------
    _spec(
        "low-karma figure → 403",
        lambda: _expect_refused(
            b,
            (403,),
            file_bytes=_PNG,
            filename="b.png",
            content_type="image/png",
            purpose="figure",
        ),
    )

    # ---- 3. avatar is exempt from the karma gate ------------------------
    def _check_avatar():
        resp = _upload_ok(
            b,
            file_bytes=_PNG,
            filename="b-avatar.png",
            content_type="image/png",
            purpose="avatar",
        )
        url = resp.get("url", "") if isinstance(resp, dict) else ""
        if not _is_content_addressed(url):
            raise _SpecViolation(f"expected a content-addressed URL, got {url!r}")

    _spec("low-karma avatar → 200 (exempt)", _check_avatar)

    # ---- 3. new figure costs coins and is content-addressed -------------
    # Sentinel for the object-store-dependent steps: if this does not produce
    # a content-addressed URL, the endpoint is not live, and steps 4-6 are
    # skipped rather than risk a false pass.
    live = False
    coins_before = me_a.get("remaining_coins", 0)
    try:
        resp = _upload_ok(
            a,
            file_bytes=_PNG,
            filename="a.png",
            content_type="image/png",
            purpose="figure",
        )
        url = resp.get("url", "") if isinstance(resp, dict) else ""
        if not _is_content_addressed(url):
            raise _SpecViolation(f"expected a content-addressed URL, got {url!r}")
        coins_after = a.get("/api/v1/me")["remaining_coins"]
        if coins_before - coins_after != _COIN_COST:
            raise _SpecViolation(
                f"expected {_COIN_COST} coins charged, "
                f"got {coins_before - coins_after}"
            )
    except (_SpecViolation, ApiError) as e:
        note(TAG, "new figure → content-addressed URL, costs 2 coins", "XFAIL", str(e))
    else:
        ok(TAG, "new figure → content-addressed URL, costs 2 coins", f"url={url}")
        live = True

    # ---- 4. identical bytes are free and deduplicate --------------------
    # Only meaningful when the endpoint is live: the legacy endpoint returns
    # the same placeholder URL for any bytes and charges nothing, which would
    # be a false pass for "same URL, no coin charge".
    if live:
        def _check_dedup():
            resp = _upload_ok(
                a,
                file_bytes=_PNG,
                filename="a-again.png",
                content_type="image/png",
                purpose="figure",
            )
            again = resp.get("url", "") if isinstance(resp, dict) else ""
            if again != url:
                raise _SpecViolation(f"expected the same URL, got {again!r}")
            coins_now = a.get("/api/v1/me")["remaining_coins"]
            if coins_now != coins_after:
                raise _SpecViolation(
                    f"re-upload must be free, but coins changed by {coins_now - coins_after}"
                )

        _spec("identical bytes are free and deduplicate", _check_dedup)
    else:
        note(TAG, "identical bytes are free and deduplicate", "SKIP", "endpoint not live")

    # ---- 5. non-image bytes → 415 ---------------------------------------
    _spec(
        "non-image bytes → 415",
        lambda: _expect_refused(
            a,
            (415,),
            file_bytes=b"this is definitely not an image",
            filename="fake.png",
            content_type="image/png",
            purpose="figure",
        ),
    )

    # ---- 6. oversize → refused ------------------------------------------
    _spec(
        "oversize file → 413/422",
        lambda: _expect_refused(
            a,
            (413, 422),
            file_bytes=b"\x00" * (5_000_000 + 1),
            filename="big.png",
            content_type="image/png",
            purpose="figure",
        ),
    )

    # ---- 7. legacy vditor endpoint is gone ------------------------------
    def _check_vditor():
        try:
            a.upload(
                "/api/v1/upload/vditor/",
                file_bytes=_PNG,
                filename="a.png",
                content_type="image/png",
            )
        except ApiError as e:
            if e.status_code == 404:
                return
            raise _SpecViolation(f"expected 404, got {e.status_code}") from None
        raise _SpecViolation("expected 404, but the endpoint still exists")

    _spec("vditor endpoint removed → 404", _check_vditor)


if __name__ == "__main__":
    from scenarios import bootstrap

    run(bootstrap.build_state())
