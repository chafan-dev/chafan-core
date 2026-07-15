"""s06 — submission lifecycle.

A creates a submission in the test site and edits it.

Stores state["submission_uuid"].
"""
from __future__ import annotations

import time

from client import ok, richtext

TAG = "s06_submission"


def run(state: dict) -> None:
    a = state["a"]
    cfg = state["cfg"]

    marker = f"smoke-test submission {int(time.time())}"
    created = a.post(
        "/api/v1/submissions/",
        {
            "site_uuid": cfg["site_uuid"],
            "title": marker,
            "url": "https://cha.fan/",
        },
    )
    submission_uuid = created["uuid"]
    state["submission_uuid"] = submission_uuid
    ok(TAG, "POST /submissions/", f"uuid={submission_uuid}")

    got = a.get(f"/api/v1/submissions/{submission_uuid}")
    assert got.get("uuid") == submission_uuid, f"submission round-trip failed: {got!r}"
    assert got.get("title") == marker, f"title did not round-trip: {got!r}"
    ok(TAG, "GET /submissions/{uuid}")

    a.put(
        f"/api/v1/submissions/{submission_uuid}",
        {"desc": richtext("smoke-test submission description")},
    )
    ok(TAG, "PUT /submissions/{uuid}")


if __name__ == "__main__":
    from scenarios import bootstrap
    run(bootstrap.build_state())
