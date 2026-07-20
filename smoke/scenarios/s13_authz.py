"""s13 — authorization / negative paths.

Every other scenario is a happy path. This one asserts the backend *rejects*
what it should, which catches a whole class of authz regressions cheaply:

  1. Anonymous (no token) writes are refused — login-gated endpoints return
     401 when the Authorization header is absent (OAuth2 auto_error).
  2. Anonymous access to a login-gated read (/notifications/unread/) is 401.
  3. A non-author cannot edit someone else's answer — author-only, 400.
  4. A non-author cannot delete someone else's answer — author-only, 400.

Note on why we target *answers*, not questions: in this site both A and B are
members, and question editing is wiki-style (any site member may edit), so
"B edits A's question" is *allowed* by design and would be a bad negative.
Answer edit/delete is strictly author-only, so B acting on A's answer is a
true permission denial.

Runs before s08_delete so A's answer still exists; the rejected delete in (4)
leaves it intact.
"""
from __future__ import annotations

import uuid as uuidlib

from client import ApiClient, expect_error, ok, richtext

TAG = "s13_authz"


def run(state: dict) -> None:
    a = state["a"]
    b = state["b"]
    cfg = state["cfg"]
    question_uuid = state["question_uuid"]
    answer_uuid = state["answer_uuid"]

    # Fresh client with no token → sends no Authorization header.
    anon = ApiClient(cfg["api_base"], "anon")

    # ---- 1. anonymous write is refused (401) ---------------------------
    with expect_error(401):
        anon.post(
            "/api/v1/questions/",
            {"site_uuid": cfg["site_uuid"], "title": "should-never-persist"},
        )
    ok(TAG, "anon POST /questions/ → 401")

    with expect_error(401):
        anon.post(
            "/api/v1/answers/",
            {
                "question_uuid": question_uuid,
                "content": richtext("should-never-persist"),
                "is_published": True,
                "visibility": "anyone",
                "writing_session_uuid": str(uuidlib.uuid4()),
            },
        )
    ok(TAG, "anon POST /answers/ → 401")

    # ---- 2. anonymous login-gated read is refused (401) ----------------
    with expect_error(401):
        anon.get("/api/v1/notifications/unread/")
    ok(TAG, "anon GET /notifications/unread/ → 401")

    # ---- 3. non-author cannot edit A's answer (400) --------------------
    with expect_error(400):
        b.put(
            f"/api/v1/answers/{answer_uuid}",
            {
                "updated_content": richtext("B should not be able to write this"),
                "is_draft": False,
                "visibility": "anyone",
            },
        )
    ok(TAG, "B PUT A's answer → 400 (author-only)")

    # ---- 4. non-author cannot delete A's answer (400) ------------------
    # Rejected, so A's answer survives for s08_delete.
    with expect_error(400):
        b.delete(f"/api/v1/answers/{answer_uuid}")
    ok(TAG, "B DELETE A's answer → 400 (author-only)")

    # The answer must still be there for s08.
    still_there = a.get(f"/api/v1/answers/{answer_uuid}")
    assert still_there.get("uuid") == answer_uuid, (
        f"A's answer vanished after rejected delete: {still_there!r}"
    )
    ok(TAG, "A's answer still intact")


if __name__ == "__main__":
    from scenarios import bootstrap
    run(bootstrap.build_state())
