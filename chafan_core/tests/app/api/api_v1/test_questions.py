import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.config import settings
from chafan_core.tests.conftest import ensure_user_has_coins, ensure_user_in_site
from chafan_core.tests.utils.utils import random_lower_string


# =============================================================================
# CREATE Question Tests
# =============================================================================


def test_create_question_unauthenticated(
    client: TestClient,
    example_site_uuid: str,
) -> None:
    """Test that unauthenticated users cannot create questions."""
    r = client.post(
        f"{settings.API_V1_STR}/questions/",
        json={"site_uuid": example_site_uuid},
    )
    assert r.status_code == 401


def test_create_question_invalid_site(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
) -> None:
    """Test that creating a question with an invalid site returns an error."""
    r = client.post(
        f"{settings.API_V1_STR}/questions/",
        headers=normal_user_token_headers,
        json={
            "site_uuid": "invalid-site-uuid",
            "title": "example title",
            "description": "",
        },
    )
    assert r.status_code == 400

    # Verify the invalid site doesn't exist
    db_site = crud.site.get_by_uuid(db, uuid="invalid-site-uuid")
    assert db_site is None


def test_create_question_not_site_member(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_id: int,
    example_site_uuid: str,
) -> None:
    """Test that non-members cannot create questions in a site."""
    # Remove user from site if they are a member
    db.expire_all()
    site = crud.site.get_by_uuid(db, uuid=example_site_uuid)
    assert site is not None, f"Site {example_site_uuid} not found"
    crud.profile.remove_by_user_and_site(db, owner_id=normal_user_id, site_id=site.id)

    data = {
        "site_uuid": example_site_uuid,
        "title": "test question",
        "description": random_lower_string(),
    }

    r = client.post(
        f"{settings.API_V1_STR}/questions/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 400


def test_create_question_success(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    normal_user_id: int,
    normal_user_uuid: str,
    example_site_uuid: str,
) -> None:
    """Test successful question creation and verify data in PostgreSQL."""
    # Ensure user is a site member
    ensure_user_in_site(
        client, db, normal_user_id, normal_user_uuid,
        example_site_uuid, superuser_token_headers
    )

    title = f"Test Question {random_lower_string()}"
    description = random_lower_string()
    data = {
        "site_uuid": example_site_uuid,
        "title": title,
        "description": description,
    }

    r = client.post(
        f"{settings.API_V1_STR}/questions/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert 200 <= r.status_code < 300, r.text
    created = r.json()
    assert "author" in created
    assert "uuid" in created
    assert created["author"]["uuid"] == normal_user_uuid
    question_uuid = created["uuid"]

    # Verify data is stored correctly in PostgreSQL
    db.expire_all()
    db_question = crud.question.get_by_uuid(db, uuid=question_uuid)
    assert db_question is not None, "Question not found in database"
    assert db_question.title == title
    # TODO: QuestionCreate schema doesn't support description field yet
    # assert db_question.description is not None
    assert db_question.author_id == normal_user_id
    assert db_question.created_at is not None

    # Verify site relationship
    site = crud.site.get_by_uuid(db, uuid=example_site_uuid)
    assert site is not None, f"Site {example_site_uuid} not found"
    assert db_question.site_id == site.id


# =============================================================================
# GET Question Tests
# =============================================================================


def test_get_question_success(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    normal_user_id: int,
    normal_user_uuid: str,
    example_site_uuid: str,
) -> None:
    """Test getting a question and verify data matches PostgreSQL."""
    # Ensure user is a site member
    ensure_user_in_site(
        client, db, normal_user_id, normal_user_uuid,
        example_site_uuid, superuser_token_headers
    )

    # First create a question
    title = f"Question to get {random_lower_string()}"
    data = {
        "site_uuid": example_site_uuid,
        "title": title,
        "description": random_lower_string(),
    }

    r = client.post(
        f"{settings.API_V1_STR}/questions/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    question_uuid = r.json()["uuid"]

    # Get the question
    r = client.get(
        f"{settings.API_V1_STR}/questions/{question_uuid}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    response_data = r.json()
    assert response_data["uuid"] == question_uuid
    assert response_data["title"] == title

    # Verify response matches database
    db.expire_all()
    db_question = crud.question.get_by_uuid(db, uuid=question_uuid)
    assert db_question is not None
    assert db_question.title == response_data["title"]
    assert db_question.uuid == response_data["uuid"]


def test_get_question_nonexistent(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
) -> None:
    """Test that getting a nonexistent question returns an error."""
    r = client.get(
        f"{settings.API_V1_STR}/questions/invalid-uuid",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 404

    # Verify it doesn't exist in database
    db_question = crud.question.get_by_uuid(db, uuid="invalid-uuid")
    assert db_question is None


# =============================================================================
# UPDATE Question Tests
# =============================================================================


@pytest.mark.skip(reason="TODO: QuestionCreate doesn't support description, QuestionUpdate uses 'desc' (RichText) not 'description'")
def test_update_question_as_author(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    normal_user_id: int,
    normal_user_uuid: str,
    example_site_uuid: str,
) -> None:
    """Test updating a question as author and verify in PostgreSQL."""
    # Ensure user is a site member
    ensure_user_in_site(
        client, db, normal_user_id, normal_user_uuid,
        example_site_uuid, superuser_token_headers
    )

    # First create a question
    original_description = random_lower_string()
    data = {
        "site_uuid": example_site_uuid,
        "title": f"Question to update {random_lower_string()}",
        "description": original_description,
    }

    r = client.post(
        f"{settings.API_V1_STR}/questions/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    question_uuid = r.json()["uuid"]

    # Verify original description in database
    db.expire_all()
    db_question_before = crud.question.get_by_uuid(db, uuid=question_uuid)
    assert db_question_before is not None, f"Question {question_uuid} not found"
    assert original_description in db_question_before.description

    # Update the question
    new_description = f"Updated description {random_lower_string()}"
    r = client.put(
        f"{settings.API_V1_STR}/questions/{question_uuid}",
        headers=normal_user_token_headers,
        json={"site_uuid": example_site_uuid, "description": new_description},
    )
    assert r.status_code == 200

    # Verify updated description in PostgreSQL
    db.expire_all()
    db_question_after = crud.question.get_by_uuid(db, uuid=question_uuid)
    assert db_question_after is not None
    assert new_description in db_question_after.description


@pytest.mark.skip(reason="TODO: QuestionCreate doesn't support description, QuestionUpdate uses 'desc' (RichText) not 'description'")
def test_update_question_as_non_author(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    moderator_user_token_headers: dict,
    normal_user_id: int,
    normal_user_uuid: str,
    example_site_uuid: str,
) -> None:
    """Test that non-authors cannot update questions."""
    # Ensure user is a site member
    ensure_user_in_site(
        client, db, normal_user_id, normal_user_uuid,
        example_site_uuid, superuser_token_headers
    )

    # Create a question as normal user
    original_description = random_lower_string()
    data = {
        "site_uuid": example_site_uuid,
        "title": f"Question by normal user {random_lower_string()}",
        "description": original_description,
    }

    r = client.post(
        f"{settings.API_V1_STR}/questions/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    question_uuid = r.json()["uuid"]

    # Try to update as moderator (non-author)
    r = client.put(
        f"{settings.API_V1_STR}/questions/{question_uuid}",
        headers=moderator_user_token_headers,
        json={"site_uuid": example_site_uuid, "description": "Unauthorized update"},
    )
    assert r.status_code == 400

    # Verify data was NOT changed in PostgreSQL
    db.expire_all()
    db_question = crud.question.get_by_uuid(db, uuid=question_uuid)
    assert db_question is not None, f"Question {question_uuid} not found"
    assert original_description in db_question.description


def test_update_question_nonexistent(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    example_site_uuid: str,
) -> None:
    """Test that updating a nonexistent question returns an error."""
    r = client.put(
        f"{settings.API_V1_STR}/questions/invalid-uuid",
        headers=normal_user_token_headers,
        json={"site_uuid": example_site_uuid, "description": "Updated"},
    )
    assert r.status_code == 400

    # Verify it doesn't exist in database
    db_question = crud.question.get_by_uuid(db, uuid="invalid-uuid")
    assert db_question is None


# =============================================================================
# Views Counter Tests
# =============================================================================


def test_bump_question_views(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    normal_user_id: int,
    normal_user_uuid: str,
    example_site_uuid: str,
) -> None:
    """Test bumping views counter for a question."""
    # Ensure user is a site member
    ensure_user_in_site(
        client, db, normal_user_id, normal_user_uuid,
        example_site_uuid, superuser_token_headers
    )

    # Create a question
    data = {
        "site_uuid": example_site_uuid,
        "title": f"Question for views {random_lower_string()}",
        "description": random_lower_string(),
    }

    r = client.post(
        f"{settings.API_V1_STR}/questions/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    question_uuid = r.json()["uuid"]

    # Bump views
    r = client.post(f"{settings.API_V1_STR}/questions/{question_uuid}/views/")
    assert r.status_code == 200

    # Verify question still exists in database
    db.expire_all()
    db_question = crud.question.get_by_uuid(db, uuid=question_uuid)
    assert db_question is not None


def test_bump_views_nonexistent_question(
    client: TestClient,
    db: Session,
) -> None:
    """Test that bumping views for a nonexistent question returns an error."""
    r = client.post(f"{settings.API_V1_STR}/questions/invalid-uuid/views/")
    assert r.status_code == 400

    # Verify it doesn't exist in database
    db_question = crud.question.get_by_uuid(db, uuid="invalid-uuid")
    assert db_question is None


# =============================================================================
# Upvotes Tests
# =============================================================================


def test_get_question_upvotes(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    normal_user_id: int,
    normal_user_uuid: str,
    example_site_uuid: str,
) -> None:
    """Test getting upvotes for a question."""
    # Ensure user is a site member
    ensure_user_in_site(
        client, db, normal_user_id, normal_user_uuid,
        example_site_uuid, superuser_token_headers
    )

    # Create a question
    data = {
        "site_uuid": example_site_uuid,
        "title": f"Question for upvotes {random_lower_string()}",
        "description": random_lower_string(),
    }

    r = client.post(
        f"{settings.API_V1_STR}/questions/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    question_uuid = r.json()["uuid"]

    # Get upvotes
    r = client.get(
        f"{settings.API_V1_STR}/questions/{question_uuid}/upvotes/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "count" in data
    assert "upvoted" in data

    # Verify question exists in database with correct upvotes_count
    db.expire_all()
    db_question = crud.question.get_by_uuid(db, uuid=question_uuid)
    assert db_question is not None
    assert db_question.upvotes_count == data["count"]


# =============================================================================
# Archive Atomicity Tests
# =============================================================================


def _create_question(
    client: TestClient,
    normal_user_token_headers: dict,
    example_site_uuid: str,
) -> str:
    r = client.post(
        f"{settings.API_V1_STR}/questions/",
        headers=normal_user_token_headers,
        json={
            "site_uuid": example_site_uuid,
            "title": f"Question for archives {random_lower_string()}",
        },
    )
    assert r.status_code == 200, r.json()
    return r.json()["uuid"]


def test_rejected_question_update_writes_no_archive(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    normal_user_id: int,
    normal_user_uuid: str,
    example_site_uuid: str,
) -> None:
    """A rejected edit must leave no trace.

    update_question used to commit the QuestionArchive before validating
    topic_uuids, so a 400 rolled back the update but kept an archive row
    describing a revision that never happened.
    """
    ensure_user_in_site(
        client, db, normal_user_id, normal_user_uuid,
        example_site_uuid, superuser_token_headers
    )
    ensure_user_has_coins(db, normal_user_id, coins=100)
    question_uuid = _create_question(
        client, normal_user_token_headers, example_site_uuid
    )

    db.expire_all()
    question = crud.question.get_by_uuid(db, uuid=question_uuid)
    assert question is not None
    original_title = question.title
    archives_before = len(question.archives)

    r = client.put(
        f"{settings.API_V1_STR}/questions/{question_uuid}",
        headers=normal_user_token_headers,
        json={
            "title": f"Rejected update {random_lower_string()}",
            "topic_uuids": ["nonexistent-topic-uuid"],
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "The topic doesn't exist."

    db.expire_all()
    question = crud.question.get_by_uuid(db, uuid=question_uuid)
    assert question is not None
    assert len(question.archives) == archives_before, (
        "rejected update left an orphan archive row"
    )
    assert question.title == original_title


def test_repeated_rejected_updates_write_no_archives(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    normal_user_id: int,
    normal_user_uuid: str,
    example_site_uuid: str,
) -> None:
    """Retrying a rejected edit must not accumulate archive rows."""
    ensure_user_in_site(
        client, db, normal_user_id, normal_user_uuid,
        example_site_uuid, superuser_token_headers
    )
    ensure_user_has_coins(db, normal_user_id, coins=100)
    question_uuid = _create_question(
        client, normal_user_token_headers, example_site_uuid
    )

    db.expire_all()
    question = crud.question.get_by_uuid(db, uuid=question_uuid)
    assert question is not None
    archives_before = len(question.archives)

    for _ in range(3):
        r = client.put(
            f"{settings.API_V1_STR}/questions/{question_uuid}",
            headers=normal_user_token_headers,
            json={
                "title": f"Rejected {random_lower_string()}",
                "topic_uuids": ["nonexistent-topic-uuid"],
            },
        )
        assert r.status_code == 400

    db.expire_all()
    question = crud.question.get_by_uuid(db, uuid=question_uuid)
    assert question is not None
    assert len(question.archives) == archives_before


def test_accepted_question_update_writes_one_archive(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    normal_user_id: int,
    normal_user_uuid: str,
    example_site_uuid: str,
) -> None:
    """Happy path still archives: removing the mid-function commit must not
    stop a successful edit from recording its prior revision."""
    ensure_user_in_site(
        client, db, normal_user_id, normal_user_uuid,
        example_site_uuid, superuser_token_headers
    )
    ensure_user_has_coins(db, normal_user_id, coins=100)
    question_uuid = _create_question(
        client, normal_user_token_headers, example_site_uuid
    )

    db.expire_all()
    question = crud.question.get_by_uuid(db, uuid=question_uuid)
    assert question is not None
    original_title = question.title
    archives_before = len(question.archives)

    new_title = f"Accepted update {random_lower_string()}"
    r = client.put(
        f"{settings.API_V1_STR}/questions/{question_uuid}",
        headers=normal_user_token_headers,
        json={"title": new_title},
    )
    assert r.status_code == 200, r.json()

    db.expire_all()
    question = crud.question.get_by_uuid(db, uuid=question_uuid)
    assert question is not None
    assert question.title == new_title
    assert len(question.archives) == archives_before + 1
    assert original_title in [a.title for a in question.archives]


# =============================================================================
# Archive Authorization Tests
# =============================================================================


def test_get_question_archives_as_author(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    normal_user_id: int,
    normal_user_uuid: str,
    example_site_uuid: str,
) -> None:
    """The author (a site member) can read revision history."""
    ensure_user_in_site(
        client, db, normal_user_id, normal_user_uuid,
        example_site_uuid, superuser_token_headers
    )
    ensure_user_has_coins(db, normal_user_id, coins=100)
    question_uuid = _create_question(
        client, normal_user_token_headers, example_site_uuid
    )

    r = client.get(
        f"{settings.API_V1_STR}/questions/{question_uuid}/archives/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_question_archives_unauthenticated(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    normal_user_id: int,
    normal_user_uuid: str,
    example_site_uuid: str,
) -> None:
    """Anonymous callers must not read revision history of a private site.

    list_archives previously performed no permission check at all, so question
    revision history was world-readable regardless of site visibility.
    """
    ensure_user_in_site(
        client, db, normal_user_id, normal_user_uuid,
        example_site_uuid, superuser_token_headers
    )
    ensure_user_has_coins(db, normal_user_id, coins=100)
    question_uuid = _create_question(
        client, normal_user_token_headers, example_site_uuid
    )

    r = client.get(f"{settings.API_V1_STR}/questions/{question_uuid}/archives/")
    assert r.status_code != 200, "anonymous read of private-site archives"
    assert r.status_code in (400, 401, 403, 404)


# =============================================================================
# Background Postprocess Tests
# =============================================================================


def test_new_question_writes_activity_and_feed(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    moderator_user_token_headers: dict,
    normal_user_id: int,
    normal_user_uuid: str,
    moderator_user_id: int,
    example_site_uuid: str,
) -> None:
    """postprocess_new_question must persist both the Activity and its feed fanout.

    These run under execute_with_broker, which has no request boundary; the
    Activity used to be committed mid-function before new_activity_into_feed
    ran. Removing that commit means the flush alone has to assign activity.id,
    and the single boundary at the end has to cover both writes.
    """
    ensure_user_in_site(
        client, db, normal_user_id, normal_user_uuid,
        example_site_uuid, superuser_token_headers
    )
    ensure_user_has_coins(db, normal_user_id, coins=100)

    # Feed rows fan out to the subject's followers, so give the author one.
    r = client.post(
        f"{settings.API_V1_STR}/me/follows/{normal_user_uuid}",
        headers=moderator_user_token_headers,
    )
    assert r.status_code == 200, r.json()

    question_uuid = _create_question(
        client, normal_user_token_headers, example_site_uuid
    )

    db.expire_all()
    question = crud.question.get_by_uuid(db, uuid=question_uuid)
    assert question is not None

    activities = (
        db.query(models.Activity).filter_by(site_id=question.site_id).all()
    )
    assert activities, "postprocess_new_question persisted no Activity"
    activity_ids = [a.id for a in activities]

    feeds = (
        db.query(models.Feed)
        .filter(
            models.Feed.receiver_id == moderator_user_id,
            models.Feed.activity_id.in_(activity_ids),
        )
        .all()
    )
    assert feeds, "Activity landed but its feed fanout did not"
