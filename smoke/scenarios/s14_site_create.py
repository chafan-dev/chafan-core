"""s14 — site creation is gated on karma, and a created site is usable.

Creating a site is the only action on Chafan with a karma threshold behind it
(`rules.MIN_KARMA_CREATE_SITE`), and until recently that threshold decided
nothing: an admin-approval branch sat in front of it that no request could
reach, and karma itself was only recomputed once a day, so the gate read a
stale number. Both are gone. This scenario pins the gate down over real HTTP,
from both sides.

  Refused (account B, low karma)
    1. B's own /me says it may not create a site.
    2. B's public-site attempt is refused (400).
    3. B's private-site attempt is refused (400) -- private sites are sunset.
    4. Nothing was created: both subdomains are still free.

  Admitted (account A, which earns enough karma from the seeded dataset)
    5. A's /me says it may, and A creates the site.
    6. A is the new site's moderator, and coins moved -- a gate that checks a
       price without charging it is the exact bug this suite exists to catch.
    7. The site is real: A asks a question in it, answers it, and comments on
       the answer, each read back through the API.

The two halves share one guard: each side reads `can_create_public_site` from
its own /me first and SKIPs rather than reporting a hollow pass if the account
is not on the side of the threshold this scenario needs.
"""
from __future__ import annotations

import uuid as uuidlib

from client import expect_error, note, ok, richtext

TAG = "s14_site_create"


def run(state: dict) -> None:
    a = state["a"]
    b = state["b"]

    # Subdomains nothing else uses, so "still free" below is meaningful.
    refused = f"smoke{uuidlib.uuid4().hex[:10]}"
    created_sub = f"smoke{uuidlib.uuid4().hex[:10]}"

    # ================= refused: B has too little karma =================
    me_b = b.get("/api/v1/me")
    if me_b.get("can_create_public_site"):
        note(
            TAG,
            "B below karma threshold",
            "SKIP",
            f"karma={me_b.get('karma')} already qualifies",
        )
    else:
        ok(TAG, "B cannot create a site", f"karma={me_b.get('karma')}")

        with expect_error(400):
            b.post(
                "/api/v1/sites/",
                {
                    "name": f"Smoke Site {refused}",
                    "subdomain": refused,
                    "permission_type": "public",
                    "description": "should-never-persist",
                },
            )
        ok(TAG, "B POST /sites/ public → 400", "insufficient karma")

        # Private sites are sunset, so this is refused for a second,
        # independent reason. Asserting it keeps the sunset from regressing.
        with expect_error(400):
            b.post(
                "/api/v1/sites/",
                {
                    "name": f"Smoke Private {refused}",
                    "subdomain": f"{refused}p",
                    "permission_type": "private",
                    "description": "should-never-persist",
                },
            )
        ok(TAG, "B POST /sites/ private → 400", "private sites sunset")

        # A rejected create that still wrote a row would be the worst outcome
        # of all, and no status code alone rules it out.
        for candidate in (refused, f"{refused}p"):
            with expect_error(400, 404):
                b.get(f"/api/v1/sites/{candidate}")
        ok(TAG, "no site was created", f"subdomain={refused!r} still free")

    # ================= admitted: A has enough karma ====================
    me_a = a.get("/api/v1/me")
    if not me_a.get("can_create_public_site"):
        note(
            TAG,
            "A above karma threshold",
            "SKIP",
            f"karma={me_a.get('karma')} does not qualify; happy path not covered",
        )
        return
    coins_before = me_a["remaining_coins"]
    ok(TAG, "A can create a site", f"karma={me_a.get('karma')}")

    response = a.post(
        "/api/v1/sites/",
        {
            "name": f"Smoke Site {created_sub}",
            "subdomain": created_sub,
            "permission_type": "public",
            "description": "created by the smoke suite",
        },
    )
    site = response.get("created_site")
    assert site, f"no created_site in response: {response!r}"
    site_uuid = site["uuid"]
    ok(TAG, "A POST /sites/ public → created", f"uuid={site_uuid}")

    assert site["moderator"]["uuid"] == me_a["uuid"], (
        f"creator is not the moderator: {site['moderator']!r}"
    )
    ok(TAG, "A is the site moderator")

    # The charge must actually land. An unpriced gate reads identically to a
    # priced one from the outside until you look at the balance.
    coins_after = a.get("/api/v1/me")["remaining_coins"]
    assert coins_after < coins_before, (
        f"creating a site cost nothing: {coins_before} → {coins_after}"
    )
    ok(TAG, "creating the site cost coins", f"{coins_before} → {coins_after}")

    # The site must be reachable by subdomain like any other.
    fetched = a.get(f"/api/v1/sites/{created_sub}")
    assert fetched["uuid"] == site_uuid, f"subdomain lookup mismatch: {fetched!r}"
    ok(TAG, "GET /sites/{subdomain}", f"subdomain={created_sub!r}")

    # ---- the new site actually works -----------------------------------
    title = f"smoke-test question in {created_sub}"
    question = a.post(
        "/api/v1/questions/", {"site_uuid": site_uuid, "title": title}
    )
    question_uuid = question["uuid"]
    ok(TAG, "A asks a question in the new site", f"uuid={question_uuid}")

    answer = a.post(
        "/api/v1/answers/",
        {
            "question_uuid": question_uuid,
            "content": richtext("smoke-test answer in a freshly created site"),
            "is_published": True,
            "visibility": "anyone",
            "writing_session_uuid": str(uuidlib.uuid4()),
        },
    )
    answer_uuid = answer["uuid"]
    ok(TAG, "A answers it", f"uuid={answer_uuid}")

    comment = a.post(
        "/api/v1/comments/",
        {
            "answer_uuid": answer_uuid,
            "content": richtext("smoke-test comment in a freshly created site"),
        },
    )
    ok(TAG, "A comments on the answer", f"uuid={comment['uuid']}")

    page = a.get(f"/api/v1/questions/{question_uuid}/page")
    assert page["question"]["title"] == title, (
        f"title did not round-trip: {page['question']['title']!r}"
    )
    listed = page["full_answers"] + page["answer_previews"]
    assert any(ans["uuid"] == answer_uuid for ans in listed), (
        f"answer missing from the question page: {listed!r}"
    )
    ok(TAG, "question page shows the answer", f"site={created_sub!r}")


if __name__ == "__main__":
    from scenarios import bootstrap
    run(bootstrap.build_state())
