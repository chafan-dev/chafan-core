"""s07 — article lifecycle.

A creates a draft article in the configured column, then publishes it.
The column must be owned by A.

Stores state["article_uuid"].
"""
from __future__ import annotations

import time
import uuid as uuidlib

from client import ok, richtext

TAG = "s07_article"


def run(state: dict) -> None:
    a = state["a"]
    cfg = state["cfg"]

    marker = f"smoke-test article {int(time.time())}"
    created = a.post(
        "/api/v1/articles/",
        {
            "title": marker,
            "content": richtext("smoke-test article draft body"),
            "article_column_uuid": cfg["article_column_uuid"],
            "is_published": False,
            "writing_session_uuid": str(uuidlib.uuid4()),
            "visibility": "anyone",
        },
    )
    article_uuid = created["uuid"]
    state["article_uuid"] = article_uuid
    ok(TAG, "POST /articles/ (draft)", f"uuid={article_uuid}")

    got = a.get(f"/api/v1/articles/{article_uuid}")
    assert got.get("uuid") == article_uuid, f"article round-trip failed: {got!r}"
    ok(TAG, "GET /articles/{uuid}")

    published = a.put(
        f"/api/v1/articles/{article_uuid}",
        {
            "updated_title": marker + " (published)",
            "updated_content": richtext("smoke-test article published body"),
            "is_draft": False,
            "visibility": "anyone",
        },
    )
    assert published.get("is_published") is True, f"publish did not land: {published!r}"
    ok(TAG, "PUT /articles/{uuid} (publish)")


if __name__ == "__main__":
    from scenarios import bootstrap
    run(bootstrap.build_state())
