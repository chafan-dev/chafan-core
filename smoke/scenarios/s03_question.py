"""s03 — question lifecycle.

Account A creates, reads, and edits a question. Account B upvotes it — the
backend explicitly rejects author self-upvote ("Author can't upvote authored
question"), so upvotes exercise cross-account state, which is what we want
anyway.

Stores state["question_uuid"] for later scenarios.
"""
from __future__ import annotations

import time

from client import ok, richtext

TAG = "s03_question"


def run(state: dict) -> None:
    a = state["a"]
    b = state["b"]
    cfg = state["cfg"]

    marker = f"smoke-test question {int(time.time())}"
    created = a.post(
        "/api/v1/questions/",
        {"site_uuid": cfg["site_uuid"], "title": marker},
    )
    question_uuid = created["uuid"]
    state["question_uuid"] = question_uuid
    ok(TAG, "POST /questions/", f"uuid={question_uuid}")

    page = a.get(f"/api/v1/questions/{question_uuid}/page")
    assert page["question"]["title"] == marker, (
        f"title did not round-trip: {page['question']['title']!r} != {marker!r}"
    )
    ok(TAG, "GET /questions/{uuid}/page (A)")

    new_title = marker + " (edited)"
    a.put(
        f"/api/v1/questions/{question_uuid}",
        {"title": new_title, "desc": richtext("smoke-test description body")},
    )
    ok(TAG, "PUT /questions/{uuid}")

    page2 = a.get(f"/api/v1/questions/{question_uuid}/page")
    assert page2["question"]["title"] == new_title, (
        f"edit did not land: {page2['question']['title']!r}"
    )
    ok(TAG, "GET /questions/{uuid}/page after edit")

    upvotes = b.post(f"/api/v1/questions/{question_uuid}/upvotes/")
    assert upvotes["upvoted"] is True, f"upvote did not stick: {upvotes!r}"
    assert upvotes["count"] >= 1, f"upvote count not incremented: {upvotes!r}"
    ok(TAG, "POST /questions/{uuid}/upvotes/ (B)", f"count={upvotes['count']}")

    got = a.get(f"/api/v1/questions/{question_uuid}/upvotes/")
    assert got["count"] >= 1, f"upvote count read-back wrong: {got!r}"
    ok(TAG, "GET /questions/{uuid}/upvotes/")

    after_delete = b.delete(f"/api/v1/questions/{question_uuid}/upvotes/")
    assert after_delete["upvoted"] is False, f"cancel upvote failed: {after_delete!r}"
    ok(TAG, "DELETE /questions/{uuid}/upvotes/ (B)")


if __name__ == "__main__":
    from scenarios import bootstrap
    run(bootstrap.build_state())
