"""s10 — an activity reaching a reader, across every verb that fans out.

`GET /api/v1/activities/` answers two different questions and the frontend
depends on the difference:

* **the home feed** (no `subject_user_uuid`) — what was *delivered* to the
  viewer. Delivery follows the follow graph and is written by a post-response
  background task, so it is eventually consistent and polled here.
* **a profile** (`subject_user_uuid=<uuid>`) — what one user *did*. Since #183
  that reads the event log rather than the delivery table, so it does not
  depend on the subject having an audience.

The happy path is first: A follows B, B posts a question, an answer, an
article and a comment, and A finds them in their feed. Then the profile
half, then the negative case.

Two things this scenario has to work around, both deliberate product
behaviour rather than bugs:

**Comments are not fanned out.** `comment_answer` and its siblings have an
empty `feed_audience` in `services/activity_policy.py`, so B's comment reaches
B's *profile* but never A's feed. Asserted both ways below, because a test
that quietly expected it in the feed would be pinning the wrong contract.

**The home feed is padded when it is nearly empty.** `feed_fill.top_up` tops a
short feed up from recent public activity site-wide, which would let this
scenario pass even if delivery were completely broken. Padding is skipped on
any request carrying `before_activity_id`, so the feed assertions here pass one
— `_delivered()` below — and read delivery alone.
"""
from __future__ import annotations

import json
import time
import uuid as uuidlib

from client import note, ok, richtext
from poll import wait_for

TAG = "s10_feed"

# Any id above every activity: selects the whole feed while still taking the
# `before_activity_id` branch, which is what turns the padding off.
ALL_ACTIVITIES = 2**31 - 1


def _post_fresh_question(client, site_uuid: str) -> tuple[str, str]:
    marker_token = uuidlib.uuid4().hex[:12]
    title = f"smoke-test feed {marker_token} {int(time.time())}"
    created = client.post(
        "/api/v1/questions/",
        {"site_uuid": site_uuid, "title": title},
    )
    return created["uuid"], marker_token


def _activities(client, **params) -> list:
    """The activities array from one GET /activities/ call."""
    return client.get("/api/v1/activities/", limit=50, **params)["activities"]


def _delivered(client) -> list:
    """The viewer's feed with the padding suppressed -- delivery only."""
    return _activities(client, before_activity_id=ALL_ACTIVITIES)


def _delivered_contains(client, uuid: str) -> bool:
    # Cheap substring match on the serialized feed -- avoids parsing the
    # Event polymorphism, which differs per verb.
    return uuid in json.dumps(_delivered(client))


def _profile_contains(client, subject_uuid: str, uuid: str) -> bool:
    return uuid in json.dumps(_activities(client, subject_user_uuid=subject_uuid))


def _b_posts_everything(state: dict) -> dict:
    """One question, one answer, one published article, one shared comment."""
    a = state["a"]
    b = state["b"]
    cfg = state["cfg"]
    marker = uuidlib.uuid4().hex[:12]
    posted = {}

    posted["question"], _ = _post_fresh_question(b, cfg["site_uuid"])
    ok(TAG, "B creates a question", f"uuid={posted['question']}")

    # B answers their own question, and comments on their own answer, so this
    # scenario owns everything it touches: s11 also has B answer A's question,
    # and the backend allows only one answer per author per question.
    answer = b.post(
        "/api/v1/answers/",
        {
            "question_uuid": posted["question"],
            "content": richtext(f"smoke-test fanout answer {marker}"),
            "is_published": True,
            "writing_session_uuid": str(uuidlib.uuid4()),
            "visibility": "anyone",
        },
    )
    posted["answer"] = answer["uuid"]
    ok(TAG, "B answers their own question", f"uuid={posted['answer']}")

    # B needs a column of their own: articles may only be written into a column
    # the author owns, so the seeded one (A's) is not usable here.
    column = b.post(
        "/api/v1/article-columns/",
        {"name": f"smoke B column {marker}", "description": "s10"},
    )
    article = b.post(
        "/api/v1/articles/",
        {
            "title": f"smoke-test fanout article {marker}",
            "content": richtext("draft"),
            "article_column_uuid": column["uuid"],
            "is_published": False,
            "writing_session_uuid": str(uuidlib.uuid4()),
            "visibility": "anyone",
        },
    )
    posted["article"] = article["uuid"]
    # create_article is emitted at publication, not creation (#169), so the
    # draft above produces no activity at all.
    published = b.put(
        f"/api/v1/articles/{posted['article']}",
        {
            "updated_title": f"smoke-test fanout article {marker} (published)",
            "updated_content": richtext("published"),
            "is_draft": False,
            "visibility": "anyone",
        },
    )
    assert published.get("is_published") is True, f"publish did not land: {published!r}"
    ok(TAG, "B publishes an article", f"uuid={posted['article']}")

    # shared_to_timeline is what makes a comment eligible for an Activity at
    # all -- without it `events._activity_precondition` writes nothing.
    comment = b.post(
        "/api/v1/comments/",
        {
            "answer_uuid": posted["answer"],
            "content": richtext(f"smoke-test fanout comment {marker}"),
            "shared_to_timeline": True,
        },
    )
    posted["comment"] = comment["uuid"]
    ok(TAG, "B comments, shared to timeline", f"uuid={posted['comment']}")

    return posted


def run(state: dict) -> None:
    a = state["a"]
    b = state["b"]
    cfg = state["cfg"]
    timeout = float(cfg["poll_timeout_seconds"])

    # ---- happy path: everything B does reaches A -------------------------
    a.post(f"/api/v1/me/follows/{b.uuid}")
    ok(TAG, "A follows B")

    posted = _b_posts_everything(state)

    # Delivery is a background task, so poll for the last one to land rather
    # than assuming it is already there.
    _, elapsed = wait_for(
        lambda: _delivered_contains(a, posted["article"]),
        timeout=timeout,
        desc=f"A's feed never showed B's article {posted['article']}",
    )
    ok(TAG, "A polls /activities/ for B's activity", f"elapsed={elapsed:.1f}s")

    delivered = json.dumps(_delivered(a))
    for verb in ("question", "answer", "article"):
        assert posted[verb] in delivered, (
            f"A follows B but B's {verb} ({posted[verb]}) was not delivered; "
            "expected it in A's feed"
        )
    ok(TAG, "A's feed has B's question, answer and article")

    # Not a bug: every comment verb has an empty feed_audience, so a comment
    # reaches its author's profile and nobody's feed. Pinned so that changing
    # the policy has to change this line too.
    assert posted["comment"] not in delivered, (
        "B's comment was delivered to A; comment verbs have no feed_audience "
        "in services/activity_policy.py, so this pins that policy"
    )
    ok(TAG, "B's comment is not fanned out, per the policy table")

    # ---- the profile shows all four, delivered or not --------------------
    _, elapsed = wait_for(
        lambda: _profile_contains(b, b.uuid, posted["comment"]),
        timeout=timeout,
        desc=f"B's profile never showed their comment {posted['comment']}",
    )
    ok(TAG, "B's profile shows the comment nobody received", f"elapsed={elapsed:.1f}s")

    profile = json.dumps(_activities(b, subject_user_uuid=b.uuid))
    for verb, uuid in posted.items():
        assert uuid in profile, f"B's profile is missing their own {verb} ({uuid})"
    ok(TAG, "B's profile has all four")

    assert _profile_contains(a, b.uuid, posted["comment"]), (
        "A cannot see on B's profile what B can; a subject timeline depends on "
        "what the viewer may read, not on who is asking"
    )
    ok(TAG, "A sees the same activity on B's profile")

    items = _activities(b, subject_user_uuid=b.uuid)
    ids = [item["id"] for item in items]
    assert len(ids) == len(set(ids)), f"an activity appears twice: {ids}"
    ok(TAG, "profile has no duplicate activities", f"items={len(ids)}")

    assert not _profile_contains(a, a.uuid, posted["question"]), (
        "B's question showed up on A's profile; a subject timeline must be "
        "scoped to its subject"
    )
    ok(TAG, "a profile is scoped to its subject")

    empty = _activities(a, subject_user_uuid="no-such-user-uuid")
    assert empty == [], f"expected an empty timeline, got {len(empty)} items"
    ok(TAG, "unknown subject uuid is an empty timeline, not an error")

    # ---- negative: unfollow, and the new activity is not delivered --------
    a.delete(f"/api/v1/me/follows/{b.uuid}")
    ok(TAG, "A unfollows B")

    question_uuid_negative, _ = _post_fresh_question(b, cfg["site_uuid"])
    ok(TAG, "B creates a question (negative)", f"uuid={question_uuid_negative}")

    # Read via _delivered() so the padding cannot supply what delivery should
    # not. This used to be an XFAIL annotated "unfollow does not prune
    # fan-out"; checked against the database 2026-08-08, B's post-unfollow
    # activity has zero Feed rows and the leak was the padding all along.
    time.sleep(timeout)
    if _delivered_contains(a, question_uuid_negative):
        note(
            TAG,
            "GET /activities/ (negative)",
            "XFAIL",
            "unfollow did not stop delivery",
        )
    else:
        ok(TAG, "GET /activities/ (negative)", f"waited={timeout:.1f}s (no leak)")

    # But it is still on B's profile: nobody received it, B still did it.
    assert _profile_contains(b, b.uuid, question_uuid_negative), (
        "a question posted with no audience vanished from its author's own "
        "profile -- the bug #183 fixed"
    )
    ok(TAG, "B's profile shows a question posted with no audience")


if __name__ == "__main__":
    from scenarios import bootstrap
    run(bootstrap.build_state())
