"""s10 — how an activity reaches a reader.

Two different questions arrive at `GET /api/v1/activities/`, and the frontend
depends on them behaving differently:

* **the home feed** (no `subject_user_uuid`) asks what was *delivered* to the
  viewer. Delivery follows the follow graph and is written by a post-response
  background task, so it is eventually consistent — hence the polling here.
* **a profile** (`subject_user_uuid=<uuid>`) asks what one user *did*. Since
  #183 that reads the event log rather than the delivery table, so it no longer
  depends on the subject having an audience.

The second half pins the difference, using the question B posts while nobody
follows them: absent from A's feed, present on B's own profile. Before #183 it
was absent from both — no followers meant no `Feed` rows, and the profile query
read `Feed`.

The elapsed time printed on the positive poll is the feed-latency baseline
— watch it drift across deploys.
"""
from __future__ import annotations

import json
import time
import uuid as uuidlib

from client import note, ok
from poll import wait_for

TAG = "s10_feed"


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


def _feed_contains(client, uuid: str) -> bool:
    # Cheap substring match on the serialized feed — avoids parsing the
    # Event polymorphism, which differs per verb.
    return uuid in json.dumps(_activities(client))


def _profile_contains(client, subject_uuid: str, uuid: str) -> bool:
    return uuid in json.dumps(_activities(client, subject_user_uuid=subject_uuid))


def run(state: dict) -> None:
    a = state["a"]
    b = state["b"]
    cfg = state["cfg"]
    timeout = float(cfg["poll_timeout_seconds"])

    a.post(f"/api/v1/me/follows/{b.uuid}")
    ok(TAG, "A follow B")

    question_uuid_positive, _ = _post_fresh_question(b, cfg["site_uuid"])
    ok(TAG, "B creates question (positive)", f"uuid={question_uuid_positive}")

    _, elapsed = wait_for(
        lambda: _feed_contains(a, question_uuid_positive),
        timeout=timeout,
        desc=f"A's feed never showed question {question_uuid_positive}",
    )
    ok(TAG, "A polls /activities/ (positive)", f"elapsed={elapsed:.1f}s")

    a.delete(f"/api/v1/me/follows/{b.uuid}")
    ok(TAG, "A unfollow B")

    question_uuid_negative, _ = _post_fresh_question(b, cfg["site_uuid"])
    ok(TAG, "B creates question (negative)", f"uuid={question_uuid_negative}")

    # This check cannot currently tell a delivery leak from a padded feed, so
    # it reports XFAIL rather than failing.
    #
    # It was long annotated "unfollow does not prune fan-out". Checked against
    # the database on a bootstrap run 2026-08-08: B's post-unfollow activity
    # has *zero* Feed rows, so nothing was delivered to A and the fan-out is
    # behaving. What put the question in front of A is the padding — a home
    # feed under feed_fill.FILL_BELOW items is topped up from recent public
    # activity site-wide (services/feed_fill.py), which on a freshly seeded
    # deployment is most of the table.
    #
    # So this stays XFAIL for a different reason than advertised: the response
    # does not say whether an item was delivered or padded, and the public API
    # offers no other way to tell. `FeedSequence.random` would be exactly that
    # signal, but it is currently just the echoed request parameter (see #179).
    # TODO: set `random=True` when padding was used, then turn this into a hard
    # assertion — the frontend wants that distinction too, to label filler.
    time.sleep(timeout)
    if _feed_contains(a, question_uuid_negative):
        note(
            TAG,
            "GET /activities/ (negative)",
            "XFAIL",
            "cannot distinguish a delivery leak from feed padding",
        )
    else:
        ok(TAG, "GET /activities/ (negative)", f"waited={timeout:.1f}s (no leak)")

    # ---- the profile timeline ------------------------------------------
    # B has no followers now, which is precisely the case that used to yield a
    # blank profile: no audience, no Feed rows, and the old subject query read
    # Feed. The Activity row is still written by the same background task, so
    # this is polled for the same reason the feed is.
    _, elapsed = wait_for(
        lambda: _profile_contains(b, b.uuid, question_uuid_negative),
        timeout=timeout,
        desc=(
            "B's own profile never showed question "
            f"{question_uuid_negative}, posted while nobody followed them"
        ),
    )
    ok(
        TAG,
        "B's profile shows a question posted with no audience",
        f"elapsed={elapsed:.1f}s",
    )

    assert _profile_contains(b, b.uuid, question_uuid_positive), (
        "B's profile is missing the question that *was* delivered; a profile "
        "should show everything the subject did, delivered or not"
    )
    ok(TAG, "B's profile shows the delivered question too")

    assert _profile_contains(a, b.uuid, question_uuid_negative), (
        "A cannot see on B's profile what B can; the subject timeline should "
        "not depend on who is asking, only on what they may read"
    )
    ok(TAG, "A sees the same activity on B's profile")

    profile = _activities(b, subject_user_uuid=b.uuid)
    ids = [item["id"] for item in profile]
    assert len(ids) == len(set(ids)), f"an activity appears twice: {ids}"
    ok(TAG, "profile has no duplicate activities", f"items={len(ids)}")

    assert not _profile_contains(a, a.uuid, question_uuid_negative), (
        "B's question showed up on A's profile; a subject timeline must be "
        "scoped to its subject"
    )
    ok(TAG, "a profile is scoped to its subject")

    empty = _activities(a, subject_user_uuid="no-such-user-uuid")
    assert empty == [], f"expected an empty timeline, got {len(empty)} items"
    ok(TAG, "unknown subject uuid is an empty timeline, not an error")


if __name__ == "__main__":
    from scenarios import bootstrap
    run(bootstrap.build_state())
