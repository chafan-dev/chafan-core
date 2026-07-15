"""s01 — auth.

Login both accounts and confirm /me returns uuid/handle. Bootstrap has
already done the work; this scenario just prints the success lines so the
operator sees auth was exercised.
"""
from __future__ import annotations

from client import ok

TAG = "s01_auth"


def run(state: dict) -> None:
    a = state["a"]
    b = state["b"]
    assert a.token, "account A has no token after login"
    assert b.token, "account B has no token after login"
    assert a.uuid and a.handle, "account A missing uuid/handle"
    assert b.uuid and b.handle, "account B missing uuid/handle"

    ok(TAG, "login account_a")
    ok(TAG, "login account_b")
    ok(TAG, "GET /me (A)", f"handle=@{a.handle}")
    ok(TAG, "GET /me (B)", f"handle=@{b.handle}")


if __name__ == "__main__":
    from scenarios import bootstrap
    run(bootstrap.build_state())
