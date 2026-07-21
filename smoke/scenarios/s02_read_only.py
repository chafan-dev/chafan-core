"""s02 — anonymous read-only sanity.

Exercises the crawler/link-preview path. Both endpoints here are used on
the anonymous read path: a cold redis means one of them regresses first.
"""
from __future__ import annotations

from client import ok

TAG = "s02_read"


def run(state: dict) -> None:
    a = state["a"]
    cfg = state["cfg"]
    known_q = cfg["known_question_uuid"]

    page = a.anonymous_get(f"/api/v1/questions/{known_q}/page")
    assert "question" in page, (
        f"/questions/{known_q}/page response missing 'question' key: {page!r}"
    )
    q_title = page["question"].get("title")
    ok(TAG, "GET /questions/{uuid}/page", f"title={q_title!r}")

    topics = a.anonymous_get("/api/v1/category-topics/")
    assert isinstance(topics, list), (
        f"/category-topics/ expected list, got: {type(topics).__name__}"
    )
    ok(TAG, "GET /category-topics/", f"n={len(topics)}")


if __name__ == "__main__":
    from scenarios import bootstrap
    run(bootstrap.build_state())
