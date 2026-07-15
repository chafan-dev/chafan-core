"""s08 — delete (runs absolutely last).

Exercises the DELETE endpoints on the answer and question created earlier.
Runs last so s11 notifications still had A's question/answer to operate on.
This is the only cleanup-like step; other artifacts (submission, article,
messages, follow graph, notifications) are left in production intentionally.
"""
from __future__ import annotations

from client import ok

TAG = "s08_delete"


def run(state: dict) -> None:
    a = state["a"]
    answer_uuid = state["answer_uuid"]
    question_uuid = state["question_uuid"]

    a.delete(f"/api/v1/answers/{answer_uuid}")
    ok(TAG, "DELETE /answers/{uuid}")

    # TODO: DELETE /questions/ returns 405. Pending decision on whether only
    # admins can delete questions. Re-enable once the endpoint is settled.
    # a.delete(f"/api/v1/questions/{question_uuid}")
    # ok(TAG, "DELETE /questions/{uuid}")
    ok(TAG, "DELETE /questions/{uuid}", "SKIPPED (endpoint not yet available)")


if __name__ == "__main__":
    from scenarios import bootstrap
    run(bootstrap.build_state())
