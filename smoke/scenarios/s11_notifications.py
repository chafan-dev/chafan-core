"""s11 — notifications.

Sub-flow A (reply): B answers A's question, A gets a notification that
references B's answer uuid.

Sub-flow B (mention): A comments on A's answer with @handle_b in the
mentioned list (backend does not parse @ from the body — clients supply
the list explicitly via CommentCreate.mentioned). B gets a notification
that references A's comment.

Both sub-flows are polled because the fan-out is via dramatiq.
"""
from __future__ import annotations

import json
import uuid as uuidlib

from client import ok, richtext
from poll import wait_for

TAG = "s11_notify"


def _unread_contains(client, needle: str) -> bool:
    resp = client.get("/api/v1/notifications/unread/")
    return needle in json.dumps(resp)


def run(state: dict) -> None:
    a = state["a"]
    b = state["b"]
    cfg = state["cfg"]
    timeout = float(cfg["poll_timeout_seconds"])

    question_uuid = state["question_uuid"]
    a_answer_uuid = state["answer_uuid"]

    # ---- Sub-flow A: reply notification ---------------------------------
    b_answer = b.post(
        "/api/v1/answers/",
        {
            "question_uuid": question_uuid,
            "content": richtext("smoke-test B reply"),
            "is_published": True,
            "visibility": "anyone",
            "writing_session_uuid": str(uuidlib.uuid4()),
        },
    )
    b_answer_uuid = b_answer["uuid"]
    state["b_answer_uuid"] = b_answer_uuid
    ok(TAG, "B answers A's question", f"uuid={b_answer_uuid}")

    _, elapsed = wait_for(
        lambda: _unread_contains(a, b_answer_uuid),
        timeout=timeout,
        desc=f"A's notifications never referenced B's answer {b_answer_uuid}",
    )
    ok(TAG, "A polls /notifications/unread/", f"elapsed={elapsed:.1f}s")

    # ---- Sub-flow B: mention notification -------------------------------
    mention_body = f"smoke-test mention of @{b.handle}"
    created = a.post(
        "/api/v1/comments/",
        {
            "answer_uuid": a_answer_uuid,
            "content": richtext(mention_body),
            "mentioned": [b.handle],
        },
    )
    mention_comment_uuid = created["uuid"]
    ok(TAG, "A comments with mention", f"uuid={mention_comment_uuid}")

    _, elapsed = wait_for(
        lambda: _unread_contains(b, mention_comment_uuid),
        timeout=timeout,
        desc=(
            f"B's notifications never referenced mention comment "
            f"{mention_comment_uuid}"
        ),
    )
    ok(TAG, "B polls /notifications/unread/", f"elapsed={elapsed:.1f}s")


if __name__ == "__main__":
    from scenarios import bootstrap
    run(bootstrap.build_state())
