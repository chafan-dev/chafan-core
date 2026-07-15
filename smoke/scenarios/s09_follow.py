"""s09 — follow / unfollow.

Normalizes the pre-state (if A already follows B, unfollow first) so re-runs
don't skew the assertions. Leaves the final state as "A does not follow B"
so s10 starts from a known baseline.
"""
from __future__ import annotations

from client import ok

TAG = "s09_follow"


def _a_follows_b(a, b) -> bool:
    resp = a.get(f"/api/v1/me/follows/{b.uuid}")
    return bool(resp.get("followed_by_me"))


def _a_in_b_followers(a, b) -> bool:
    followers = a.get(f"/api/v1/people/{b.uuid}/followers/")
    return any(u.get("uuid") == a.uuid for u in followers)


def run(state: dict) -> None:
    a = state["a"]
    b = state["b"]

    # Normalize pre-state.
    if _a_follows_b(a, b):
        a.delete(f"/api/v1/me/follows/{b.uuid}")
    ok(TAG, "GET /me/follows/{uuid} (baseline)")

    resp = a.post(f"/api/v1/me/follows/{b.uuid}")
    assert resp.get("followed_by_me") is True, f"follow did not stick: {resp!r}"
    ok(TAG, "POST /me/follows/{uuid}")

    assert _a_in_b_followers(a, b), "A not in B's followers after follow"
    ok(TAG, "GET /people/{b}/followers/")

    followed = a.get(f"/api/v1/people/{a.uuid}/followed/")
    assert any(u.get("uuid") == b.uuid for u in followed), (
        "B not in A's followed list after follow"
    )
    ok(TAG, "GET /people/{a}/followed/")

    resp = a.delete(f"/api/v1/me/follows/{b.uuid}")
    assert resp.get("followed_by_me") is False, f"unfollow did not stick: {resp!r}"
    ok(TAG, "DELETE /me/follows/{uuid}")

    assert not _a_in_b_followers(a, b), "A still in B's followers after unfollow"
    ok(TAG, "GET /people/{b}/followers/ after unfollow")


if __name__ == "__main__":
    from scenarios import bootstrap
    run(bootstrap.build_state())
