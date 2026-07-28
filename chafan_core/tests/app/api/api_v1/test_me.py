"""Read gates on /me subscription and bookmark routes.

services/me.py fetched every subscribe/bookmark target with a bare
crud.<resource>.get_by_uuid and 400'd only when the row was missing, so an
authenticated non-member of a private site could subscribe to or bookmark
content there and read back its subscriber/bookmarker count. The read gates
live inside the responders, and these routes build a small UserXSubscription
schema instead of the full one, so they never reached them -- exactly the miss
get_readable_question_http's docstring warns about.

Every negative test below carries a control assertion that the outsider cannot
read the resource directly, so a test can never pass merely because the
fixture site stopped being private.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.config import settings
from chafan_core.tests.conftest import ensure_user_has_coins, ensure_user_in_site
from chafan_core.tests.utils.user import authentication_token_from_email
from chafan_core.tests.utils.utils import random_email, random_lower_string
from chafan_core.utils.base import get_uuid


@pytest.fixture(scope="module")
def outsider_token_headers(client: TestClient, db: Session) -> dict:
    """An authenticated user who is not a member of example_site_uuid."""
    return authentication_token_from_email(
        client=client, email=random_email(), db=db
    )


@pytest.fixture(scope="module")
def private_site_answer_uuid(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_id: int,
    normal_user_authored_question_uuid: str,
) -> str:
    """An answer by normal_user on a question in the private example site."""
    ensure_user_has_coins(db, normal_user_id, coins=100)
    body = f"Answer {random_lower_string()}"
    r = client.post(
        f"{settings.API_V1_STR}/answers/",
        headers=normal_user_token_headers,
        json={
            "question_uuid": normal_user_authored_question_uuid,
            "content": {
                "source": body,
                "rendered_text": body,
                "editor": "markdown",
            },
            "is_published": True,
            "is_autosaved": False,
            "visibility": "anyone",
            "writing_session_uuid": get_uuid(),
        },
    )
    r.raise_for_status()
    return r.json()["uuid"]


@pytest.fixture(scope="module")
def draft_article_uuid(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_id: int,
    example_article_column_uuid: str,
) -> str:
    """An unpublished article by normal_user: readable only by its author.

    Every other article fixture uses visibility "anyone" and is published, so
    the preview gate is never exercised by them.
    """
    ensure_user_has_coins(db, normal_user_id, coins=100)
    r = client.post(
        f"{settings.API_V1_STR}/articles/",
        headers=normal_user_token_headers,
        json={
            "title": f"Draft Article ({random_lower_string()})",
            "content": {"source": "Draft body.", "editor": "tiptap"},
            "article_column_uuid": example_article_column_uuid,
            "is_published": False,
            "writing_session_uuid": get_uuid(),
            "visibility": "anyone",
        },
    )
    r.raise_for_status()
    return r.json()["uuid"]


def _assert_blocked(r, what: str) -> None:
    assert r.status_code != 200, f"outsider was allowed to {what}: {r.text}"
    assert r.status_code in (400, 401, 403, 404), r.text


# =============================================================================
# Question subscriptions
# =============================================================================


def test_question_subscription_routes_reject_non_member(
    client: TestClient,
    db: Session,
    outsider_token_headers: dict,
    normal_user_authored_question_uuid: str,
) -> None:
    """A non-member can neither subscribe, unsubscribe, nor read the count."""
    uuid = normal_user_authored_question_uuid

    # Control: the private-site question is genuinely unreadable to them.
    control = client.get(
        f"{settings.API_V1_STR}/questions/{uuid}", headers=outsider_token_headers
    )
    assert control.status_code != 200, (
        "fixture site is not private; the assertions below would be vacuous"
    )

    _assert_blocked(
        client.post(
            f"{settings.API_V1_STR}/me/question-subscriptions/{uuid}",
            headers=outsider_token_headers,
        ),
        "subscribe to a private-site question",
    )
    _assert_blocked(
        client.get(
            f"{settings.API_V1_STR}/me/question-subscriptions/{uuid}",
            headers=outsider_token_headers,
        ),
        "read the subscriber count of a private-site question",
    )
    _assert_blocked(
        client.delete(
            f"{settings.API_V1_STR}/me/question-subscriptions/{uuid}",
            headers=outsider_token_headers,
        ),
        "unsubscribe from a private-site question",
    )


def test_rejected_question_subscribe_writes_no_row(
    client: TestClient,
    db: Session,
    outsider_token_headers: dict,
    normal_user_authored_question_uuid: str,
) -> None:
    """The blocked subscribe must not leave a durable subscription."""
    uuid = normal_user_authored_question_uuid
    outsider_uuid = client.get(
        f"{settings.API_V1_STR}/me", headers=outsider_token_headers
    ).json()["uuid"]

    client.post(
        f"{settings.API_V1_STR}/me/question-subscriptions/{uuid}",
        headers=outsider_token_headers,
    )

    db.expire_all()
    question = crud.question.get_by_uuid(db, uuid=uuid)
    assert question is not None
    subscriber_uuids = [u.uuid for u in question.subscribers]
    assert outsider_uuid not in subscriber_uuids


def test_question_subscription_still_works_for_member(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    normal_user_id: int,
    normal_user_uuid: str,
    example_site_uuid: str,
    normal_user_authored_question_uuid: str,
) -> None:
    """Happy path is unchanged: a site member can still subscribe."""
    ensure_user_in_site(
        client, db, normal_user_id, normal_user_uuid,
        example_site_uuid, superuser_token_headers
    )
    uuid = normal_user_authored_question_uuid

    r = client.post(
        f"{settings.API_V1_STR}/me/question-subscriptions/{uuid}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["subscribed_by_me"] is True

    r = client.get(
        f"{settings.API_V1_STR}/me/question-subscriptions/{uuid}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200, r.text

    r = client.delete(
        f"{settings.API_V1_STR}/me/question-subscriptions/{uuid}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["subscribed_by_me"] is False


# =============================================================================
# Submission subscriptions
# =============================================================================


def test_submission_subscription_routes_reject_non_member(
    client: TestClient,
    outsider_token_headers: dict,
    example_submission_uuid: str,
) -> None:
    uuid = example_submission_uuid

    control = client.get(
        f"{settings.API_V1_STR}/submissions/{uuid}", headers=outsider_token_headers
    )
    assert control.status_code != 200, (
        "fixture site is not private; the assertions below would be vacuous"
    )

    _assert_blocked(
        client.post(
            f"{settings.API_V1_STR}/me/submission-subscriptions/{uuid}",
            headers=outsider_token_headers,
        ),
        "subscribe to a private-site submission",
    )
    _assert_blocked(
        client.get(
            f"{settings.API_V1_STR}/me/submission-subscriptions/{uuid}",
            headers=outsider_token_headers,
        ),
        "read the subscriber count of a private-site submission",
    )
    _assert_blocked(
        client.delete(
            f"{settings.API_V1_STR}/me/submission-subscriptions/{uuid}",
            headers=outsider_token_headers,
        ),
        "unsubscribe from a private-site submission",
    )


def test_submission_subscription_still_works_for_member(
    client: TestClient,
    normal_user_token_headers: dict,
    example_submission_uuid: str,
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/me/submission-subscriptions/{example_submission_uuid}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["subscribed_by_me"] is True


# =============================================================================
# Answer bookmarks
# =============================================================================


def test_answer_bookmark_routes_reject_non_member(
    client: TestClient,
    outsider_token_headers: dict,
    private_site_answer_uuid: str,
) -> None:
    uuid = private_site_answer_uuid

    control = client.get(
        f"{settings.API_V1_STR}/answers/{uuid}", headers=outsider_token_headers
    )
    assert control.status_code != 200, (
        "fixture site is not private; the assertions below would be vacuous"
    )

    _assert_blocked(
        client.post(
            f"{settings.API_V1_STR}/me/answer-bookmarks/{uuid}",
            headers=outsider_token_headers,
        ),
        "bookmark a private-site answer",
    )
    _assert_blocked(
        client.delete(
            f"{settings.API_V1_STR}/me/answer-bookmarks/{uuid}",
            headers=outsider_token_headers,
        ),
        "unbookmark a private-site answer",
    )


def test_answer_bookmark_still_works_for_member(
    client: TestClient,
    normal_user_token_headers: dict,
    private_site_answer_uuid: str,
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/me/answer-bookmarks/{private_site_answer_uuid}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["bookmarked_by_me"] is True


# =============================================================================
# Article bookmarks
# =============================================================================


def test_article_bookmark_rejects_non_author_draft(
    client: TestClient,
    outsider_token_headers: dict,
    draft_article_uuid: str,
) -> None:
    """An unpublished article is readable only by its author."""
    uuid = draft_article_uuid

    control = client.get(
        f"{settings.API_V1_STR}/articles/{uuid}", headers=outsider_token_headers
    )
    assert control.status_code != 200, (
        "draft article is readable by a non-author; assertions would be vacuous"
    )

    _assert_blocked(
        client.post(
            f"{settings.API_V1_STR}/me/article-bookmarks/{uuid}",
            headers=outsider_token_headers,
        ),
        "bookmark another author's draft article",
    )
    _assert_blocked(
        client.delete(
            f"{settings.API_V1_STR}/me/article-bookmarks/{uuid}",
            headers=outsider_token_headers,
        ),
        "unbookmark another author's draft article",
    )


def test_article_bookmark_still_works_for_published_article(
    client: TestClient,
    normal_user_token_headers: dict,
    example_article_uuid: str,
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/me/article-bookmarks/{example_article_uuid}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["bookmarked_by_me"] is True


# =============================================================================
# Topics: deliberately ungated
# =============================================================================


def test_topic_subscription_is_not_site_scoped(
    client: TestClient,
    db: Session,
    outsider_token_headers: dict,
) -> None:
    """Topics carry no site and no visibility, so they stay ungated.

    Pinned so the gates added for the site-scoped resources are not extended
    here by analogy: there is nothing to leak.
    """
    topic_name = f"topic {random_lower_string()[:8]}"
    r = client.post(
        f"{settings.API_V1_STR}/topics/",
        headers=outsider_token_headers,
        json={"name": topic_name},
    )
    if r.status_code != 200:
        pytest.skip(f"topic creation unavailable: {r.status_code}")
    topic_uuid = r.json()["uuid"]

    r = client.post(
        f"{settings.API_V1_STR}/me/topic-subscriptions/{topic_uuid}",
        headers=outsider_token_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["subscribed_by_me"] is True
