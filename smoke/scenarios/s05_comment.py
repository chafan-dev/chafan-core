"""s05 — comment lifecycle.

A comments on A's own answer. B upvotes (self-upvote rejected by backend).

Stores state["comment_uuid"].
"""
from __future__ import annotations

from client import ok, richtext

TAG = "s05_comment"


def run(state: dict) -> None:
    a = state["a"]
    b = state["b"]
    answer_uuid = state["answer_uuid"]

    created = a.post(
        "/api/v1/comments/",
        {
            "answer_uuid": answer_uuid,
            "content": richtext("smoke-test comment body"),
        },
    )
    comment_uuid = created["uuid"]
    state["comment_uuid"] = comment_uuid
    ok(TAG, "POST /comments/", f"uuid={comment_uuid}")

    got = a.get(f"/api/v1/comments/{comment_uuid}")
    assert got.get("uuid") == comment_uuid, f"comment round-trip failed: {got!r}"
    ok(TAG, "GET /comments/{uuid}")

    upvotes = b.post(f"/api/v1/comments/{comment_uuid}/upvotes/")
    assert upvotes["upvoted"] is True, f"comment upvote failed: {upvotes!r}"
    ok(TAG, "POST /comments/{uuid}/upvotes/ (B)", f"count={upvotes['count']}")


if __name__ == "__main__":
    from scenarios import bootstrap
    run(bootstrap.build_state())
