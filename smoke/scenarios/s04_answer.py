"""s04 — answer lifecycle.

A answers A's own question, then B upvotes the answer. Upvote is cross-account
for the same reason as s03 (backend rejects self-upvote).

Stores state["answer_uuid"].
"""
from __future__ import annotations

import uuid as uuidlib

from client import ok, richtext

TAG = "s04_answer"


def run(state: dict) -> None:
    a = state["a"]
    b = state["b"]
    question_uuid = state["question_uuid"]

    created = a.post(
        "/api/v1/answers/",
        {
            "question_uuid": question_uuid,
            "content": richtext("smoke-test initial answer body"),
            "is_published": True,
            "visibility": "anyone",
            "writing_session_uuid": str(uuidlib.uuid4()),
        },
    )
    answer_uuid = created["uuid"]
    state["answer_uuid"] = answer_uuid
    ok(TAG, "POST /answers/", f"uuid={answer_uuid}")

    got = a.get(f"/api/v1/answers/{answer_uuid}")
    assert got.get("uuid") == answer_uuid, f"answer round-trip failed: {got!r}"
    ok(TAG, "GET /answers/{uuid}")

    a.put(
        f"/api/v1/answers/{answer_uuid}",
        {
            "updated_content": richtext("smoke-test edited answer body"),
            "is_draft": False,
            "visibility": "anyone",
        },
    )
    ok(TAG, "PUT /answers/{uuid}")

    upvotes = b.post(f"/api/v1/answers/{answer_uuid}/upvotes/")
    assert upvotes["upvoted"] is True, f"upvote did not stick: {upvotes!r}"
    assert upvotes["count"] >= 1, f"upvote count not incremented: {upvotes!r}"
    ok(TAG, "POST /answers/{uuid}/upvotes/ (B)", f"count={upvotes['count']}")


if __name__ == "__main__":
    from scenarios import bootstrap
    run(bootstrap.build_state())
