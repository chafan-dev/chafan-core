"""s11 — notifications.

Sub-flow A (reply): B answers A's question, A gets a notification that
references B's answer uuid.

Sub-flow B (mention): A comments on A's answer with @handle_b in the
mentioned list (backend does not parse @ from the body — clients supply
the list explicitly via CommentCreate.mentioned). B gets a notification
that references A's comment.

Both sub-flows are polled because the fan-out is post-response (BackgroundTasks).
"""
from __future__ import annotations

import uuid as uuidlib

from client import ok, richtext
from poll import wait_for

TAG = "s11_notify"


def _find_notification(client, *, verb: str, uuid_path: list[str], expected_uuid: str):
    """Return the unread notification whose event matches, else None.

    Stronger than a substring match on the serialized blob: the event must
    have the right ``verb`` *and* the uuid at ``uuid_path`` (e.g.
    ``["answer", "uuid"]``) must equal ``expected_uuid``. This catches a
    malformed event that merely happens to embed the uuid somewhere.
    """
    for notif in client.get("/api/v1/notifications/unread/"):
        event = notif.get("event") or {}
        if event.get("verb") != verb:
            continue
        node = event
        for key in uuid_path:
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(key)
        if node == expected_uuid:
            return notif
    return None


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

    notif, elapsed = wait_for(
        lambda: _find_notification(
            a, verb="answer_question", uuid_path=["answer", "uuid"],
            expected_uuid=b_answer_uuid,
        ),
        timeout=timeout,
        desc=(
            f"A had no 'answer_question' notification referencing B's answer "
            f"{b_answer_uuid}"
        ),
    )
    assert notif["event"]["subject"]["uuid"] == b.uuid, (
        f"reply notification actor is not B: {notif['event'].get('subject')!r}"
    )
    ok(TAG, "A polls /notifications/unread/", f"elapsed={elapsed:.1f}s verb=answer_question")

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

    notif, elapsed = wait_for(
        lambda: _find_notification(
            b, verb="mentioned_in_comment", uuid_path=["comment", "uuid"],
            expected_uuid=mention_comment_uuid,
        ),
        timeout=timeout,
        desc=(
            f"B had no 'mentioned_in_comment' notification referencing comment "
            f"{mention_comment_uuid}"
        ),
    )
    assert notif["event"]["subject"]["uuid"] == a.uuid, (
        f"mention notification actor is not A: {notif['event'].get('subject')!r}"
    )
    ok(TAG, "B polls /notifications/unread/", f"elapsed={elapsed:.1f}s verb=mentioned_in_comment")


if __name__ == "__main__":
    from scenarios import bootstrap
    run(bootstrap.build_state())
