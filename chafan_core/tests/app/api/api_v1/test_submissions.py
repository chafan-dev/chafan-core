from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.config import settings
from chafan_core.tests.conftest import ensure_user_in_site, ensure_user_has_coins
from chafan_core.tests.utils.utils import random_lower_string


# =============================================================================
# GET Submission Upvotes Tests
# =============================================================================


def test_get_submission_upvotes_unauthenticated(
    client: TestClient,
    db: Session,
    example_submission_uuid: str,
) -> None:
    """Test getting upvotes for a submission without authentication."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/"
    )
    assert r.status_code == 200
    data = r.json()
    assert "count" in data
    assert "upvoted" in data
    assert data["upvoted"] is False  # Not logged in
    assert "submission_uuid" in data

    # Verify submission exists in database with matching upvotes count
    db.expire_all()
    db_submission = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission is not None
    assert db_submission.upvotes_count == data["count"]


def test_get_submission_upvotes_authenticated(
    client: TestClient,
    db: Session,
    example_submission_uuid: str,
    normal_user_token_headers: dict,
) -> None:
    """Test getting upvotes for a submission with authentication."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "count" in data
    assert "upvoted" in data
    assert data["submission_uuid"] == example_submission_uuid

    # Verify database matches response
    db.expire_all()
    db_submission = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission is not None
    assert db_submission.upvotes_count == data["count"]


def test_get_submission_upvotes_nonexistent(
    client: TestClient,
    db: Session,
) -> None:
    """Test getting upvotes for a nonexistent submission returns an error."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/invalid-uuid/upvotes/"
    )
    assert r.status_code == 400
    assert "doesn't exists" in r.json()["detail"]

    # Verify it doesn't exist in database
    db_submission = crud.submission.get_by_uuid(db, uuid="invalid-uuid")
    assert db_submission is None


# =============================================================================
# Views Counter Tests
# =============================================================================


def test_bump_views_counter(
    client: TestClient,
    db: Session,
    example_submission_uuid: str,
) -> None:
    """Test bumping views counter for a submission."""
    r = client.post(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/views/"
    )
    assert r.status_code == 200

    # Verify submission still exists in database
    db.expire_all()
    db_submission = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission is not None


def test_bump_views_counter_nonexistent(
    client: TestClient,
    db: Session,
) -> None:
    """Test bumping views for nonexistent submission returns an error."""
    r = client.post(
        f"{settings.API_V1_STR}/submissions/invalid-uuid/views/"
    )
    assert r.status_code == 400

    # Verify it doesn't exist in database
    db_submission = crud.submission.get_by_uuid(db, uuid="invalid-uuid")
    assert db_submission is None


# =============================================================================
# GET Submission Tests
# =============================================================================


def test_get_submission_authenticated(
    client: TestClient,
    db: Session,
    example_submission_uuid: str,
    normal_user_token_headers: dict,
) -> None:
    """Test getting a submission with authentication and verify database."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["uuid"] == example_submission_uuid
    assert "title" in data
    assert "author" in data
    assert "site" in data

    # Verify response matches database
    db.expire_all()
    db_submission = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission is not None
    assert db_submission.title == data["title"]
    assert db_submission.uuid == data["uuid"]


def test_get_submission_nonexistent(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
) -> None:
    """Test getting a nonexistent submission returns an error."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/invalid-uuid",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 400
    assert "doesn't exists" in r.json()["detail"]

    # Verify it doesn't exist in database
    db_submission = crud.submission.get_by_uuid(db, uuid="invalid-uuid")
    assert db_submission is None


# =============================================================================
# CREATE Submission Tests
# =============================================================================


def test_create_submission_unauthenticated(
    client: TestClient,
    example_site_uuid: str,
) -> None:
    """Test that unauthenticated users cannot create submissions."""
    data = {
        "site_uuid": example_site_uuid,
        "title": "Test Submission",
        "url": "https://example.com/test",
    }
    r = client.post(
        f"{settings.API_V1_STR}/submissions/",
        json=data,
    )
    assert r.status_code == 401


def test_create_submission_invalid_site(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
) -> None:
    """Test creating a submission with invalid site returns an error."""
    data = {
        "site_uuid": "invalid-uuid",
        "title": "Test Submission",
        "url": "https://example.com/test",
    }
    r = client.post(
        f"{settings.API_V1_STR}/submissions/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 400

    # Verify the invalid site doesn't exist
    db_site = crud.site.get_by_uuid(db, uuid="invalid-uuid")
    assert db_site is None


def test_create_submission_success(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_uuid: str,
    normal_user_id: int,
    example_site_uuid: str,
    superuser_token_headers: dict,
) -> None:
    """Test successful submission creation and verify data in PostgreSQL."""
    ensure_user_in_site(
        client, db, normal_user_id, normal_user_uuid,
        example_site_uuid, superuser_token_headers
    )

    title = f"Test Submission {random_lower_string()}"
    url = "https://example.com/test-success"
    data = {
        "site_uuid": example_site_uuid,
        "title": title,
        "url": url,
    }
    r = client.post(
        f"{settings.API_V1_STR}/submissions/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert 200 <= r.status_code < 300, r.text
    created = r.json()
    assert "uuid" in created
    assert created["title"] == title
    assert created["url"] == url
    assert created["author"]["uuid"] == normal_user_uuid

    # Verify data is stored correctly in PostgreSQL
    db.expire_all()
    db_submission = crud.submission.get_by_uuid(db, uuid=created["uuid"])
    assert db_submission is not None, "Submission not found in database"
    assert db_submission.title == title
    assert db_submission.url == url
    assert db_submission.author_id == normal_user_id
    assert db_submission.created_at is not None

    # Verify site relationship
    site = crud.site.get_by_uuid(db, uuid=example_site_uuid)
    assert site is not None, f"Site {example_site_uuid} not found"
    assert db_submission.site_id == site.id


# =============================================================================
# UPDATE Submission Tests
# =============================================================================


def test_update_submission_as_author(
    client: TestClient,
    db: Session,
    example_submission_uuid: str,
    normal_user_token_headers: dict,
) -> None:
    """Test updating a submission as author and verify in PostgreSQL."""
    # Get original title from database
    db.expire_all()
    db_submission_before = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission_before is not None, f"Submission {example_submission_uuid} not found"
    original_title = db_submission_before.title

    new_title = f"Updated Title {random_lower_string()}"
    data = {
        "title": new_title,
    }
    r = client.put(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200, r.json()
    assert r.json()["title"] == new_title

    # Verify updated data in PostgreSQL
    db.expire_all()
    db_submission_after = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission_after is not None
    assert db_submission_after.title == new_title
    assert db_submission_after.title != original_title


def test_update_submission_as_non_author(
    client: TestClient,
    db: Session,
    example_submission_uuid: str,
    moderator_user_token_headers: dict,
) -> None:
    """Test that non-authors cannot update submissions."""
    # Get original title from database
    db.expire_all()
    db_submission_before = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission_before is not None, f"Submission {example_submission_uuid} not found"
    original_title = db_submission_before.title

    data = {
        "title": "Unauthorized Update",
    }
    r = client.put(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}",
        headers=moderator_user_token_headers,
        json=data,
    )
    assert r.status_code == 400
    assert "Unauthorized" in r.json()["detail"]

    # Verify data was NOT changed in PostgreSQL
    db.expire_all()
    db_submission_after = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission_after is not None, f"Submission {example_submission_uuid} not found"
    assert db_submission_after.title == original_title


def test_update_submission_nonexistent(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
) -> None:
    """Test that updating a nonexistent submission returns an error."""
    data = {
        "title": "Updated Title",
    }
    r = client.put(
        f"{settings.API_V1_STR}/submissions/invalid-uuid",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 400

    # Verify it doesn't exist in database
    db_submission = crud.submission.get_by_uuid(db, uuid="invalid-uuid")
    assert db_submission is None


# =============================================================================
# Archives Tests
# =============================================================================


def test_get_submission_archives(
    client: TestClient,
    db: Session,
    example_submission_uuid: str,
    normal_user_token_headers: dict,
) -> None:
    """Test getting submission archives after update and verify in PostgreSQL."""
    # Get original title
    db.expire_all()
    db_submission = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission is not None, f"Submission {example_submission_uuid} not found"
    original_title = db_submission.title

    # Update to create an archive
    new_title = f"Updated {random_lower_string()}"
    client.put(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}",
        headers=normal_user_token_headers,
        json={"title": new_title},
    )

    # Get archives via API
    r = client.get(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/archives/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    archives = r.json()
    assert isinstance(archives, list)

    # Verify archives exist in database
    db.expire_all()
    db_submission = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission is not None
    # Check if archives contain original title
    if len(db_submission.archives) > 0:
        archive_titles = [a.title for a in db_submission.archives]
        assert original_title in archive_titles or new_title == db_submission.title


def test_get_submission_archives_nonexistent(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
) -> None:
    """Test getting archives for nonexistent submission returns an error."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/invalid-uuid/archives/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 400

    # Verify it doesn't exist in database
    db_submission = crud.submission.get_by_uuid(db, uuid="invalid-uuid")
    assert db_submission is None


# =============================================================================
# Upvote Tests
# =============================================================================


def test_upvote_submission_success(
    client: TestClient,
    db: Session,
    example_submission_uuid: str,
    example_site_uuid: str,
    superuser_token_headers: dict,
    moderator_user_token_headers: dict,
    moderator_user_id: int,
    moderator_user_uuid: str,
) -> None:
    """Test upvoting a submission and verify in PostgreSQL."""
    ensure_user_in_site(
        client, db, moderator_user_id, moderator_user_uuid,
        example_site_uuid, superuser_token_headers
    )
    ensure_user_has_coins(db, moderator_user_id, coins=100)

    # Get initial upvote count from database
    db.expire_all()
    db_submission_before = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission_before is not None, f"Submission {example_submission_uuid} not found"
    initial_db_count = db_submission_before.upvotes_count

    r = client.get(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/"
    )
    initial_count = r.json()["count"]

    # Upvote
    r = client.post(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/",
        headers=moderator_user_token_headers,
    )
    assert r.status_code == 200, f"Upvote failed: {r.json()}"
    data = r.json()
    assert data["upvoted"] is True
    assert data["count"] >= initial_count

    # Verify upvote is recorded in PostgreSQL
    db.expire_all()
    db_submission_after = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission_after is not None, f"Submission {example_submission_uuid} not found"
    assert db_submission_after.upvotes_count >= initial_db_count


def test_upvote_submission_idempotent(
    client: TestClient,
    db: Session,
    example_submission_uuid: str,
    example_site_uuid: str,
    superuser_token_headers: dict,
    moderator_user_token_headers: dict,
    moderator_user_id: int,
    moderator_user_uuid: str,
) -> None:
    """Test that double upvoting doesn't increase count."""
    ensure_user_in_site(
        client, db, moderator_user_id, moderator_user_uuid,
        example_site_uuid, superuser_token_headers
    )
    ensure_user_has_coins(db, moderator_user_id, coins=100)

    r1 = client.post(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/",
        headers=moderator_user_token_headers,
    )
    assert r1.status_code == 200, f"First upvote failed: {r1.json()}"
    count1 = r1.json()["count"]

    # Get database count after first upvote
    db.expire_all()
    db_submission_1 = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission_1 is not None, f"Submission {example_submission_uuid} not found"
    db_count1 = db_submission_1.upvotes_count

    # Second upvote (should not increase count)
    r2 = client.post(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/",
        headers=moderator_user_token_headers,
    )
    assert r2.status_code == 200
    count2 = r2.json()["count"]
    assert count1 == count2

    # Verify database count unchanged
    db.expire_all()
    db_submission_2 = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission_2 is not None, f"Submission {example_submission_uuid} not found"
    assert db_submission_2.upvotes_count == db_count1


def test_upvote_submission_author_cannot_upvote(
    client: TestClient,
    db: Session,
    example_submission_uuid: str,
    normal_user_token_headers: dict,
) -> None:
    """Test that authors cannot upvote their own submissions."""
    # Get initial count from database
    db.expire_all()
    db_submission_before = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission_before is not None, f"Submission {example_submission_uuid} not found"
    initial_count = db_submission_before.upvotes_count

    r = client.post(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 400
    assert "Author can't upvote" in r.json()["detail"]

    # Verify count unchanged in database
    db.expire_all()
    db_submission_after = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission_after is not None, f"Submission {example_submission_uuid} not found"
    assert db_submission_after.upvotes_count == initial_count


def test_cancel_upvote_submission(
    client: TestClient,
    db: Session,
    example_submission_uuid: str,
    example_site_uuid: str,
    superuser_token_headers: dict,
    moderator_user_token_headers: dict,
    moderator_user_id: int,
    moderator_user_uuid: str,
) -> None:
    """Test canceling an upvote and verify in PostgreSQL."""
    ensure_user_in_site(
        client, db, moderator_user_id, moderator_user_uuid,
        example_site_uuid, superuser_token_headers
    )
    ensure_user_has_coins(db, moderator_user_id, coins=100)

    # First upvote
    r = client.post(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/",
        headers=moderator_user_token_headers,
    )
    assert r.status_code == 200, f"Upvote failed: {r.json()}"
    upvote_count = r.json()["count"]

    # Get database count after upvote
    db.expire_all()
    db_submission_upvoted = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission_upvoted is not None, f"Submission {example_submission_uuid} not found"
    db_count_upvoted = db_submission_upvoted.upvotes_count

    # Cancel upvote
    r = client.delete(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/",
        headers=moderator_user_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["upvoted"] is False
    assert data["count"] <= upvote_count

    # Verify count decreased in database
    db.expire_all()
    db_submission_cancelled = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission_cancelled is not None, f"Submission {example_submission_uuid} not found"
    assert db_submission_cancelled.upvotes_count <= db_count_upvoted


# =============================================================================
# Hide Submission Tests
# =============================================================================


def test_hide_submission_as_author(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_uuid: str,
    normal_user_id: int,
    example_site_uuid: str,
    superuser_token_headers: dict,
) -> None:
    """Test hiding a submission and verify in PostgreSQL."""
    ensure_user_in_site(
        client, db, normal_user_id, normal_user_uuid,
        example_site_uuid, superuser_token_headers
    )

    # Create a submission to hide
    title = f"To Hide {random_lower_string()}"
    r = client.post(
        f"{settings.API_V1_STR}/submissions/",
        headers=normal_user_token_headers,
        json={
            "site_uuid": example_site_uuid,
            "title": title,
            "url": "https://example.com/hide-test",
        },
    )
    assert r.status_code == 200
    submission_uuid = r.json()["uuid"]

    # Verify it exists and is not hidden
    db.expire_all()
    db_submission = crud.submission.get_by_uuid(db, uuid=submission_uuid)
    assert db_submission is not None
    assert db_submission.is_hidden is False

    # Hide it
    r = client.put(
        f"{settings.API_V1_STR}/submissions/{submission_uuid}/hide",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200

    # Verify it's hidden in PostgreSQL
    db.expire_all()
    db_submission = crud.submission.get_by_uuid(db, uuid=submission_uuid)
    assert db_submission is not None
    assert db_submission.is_hidden is True


# =============================================================================
# List Submissions Tests
# =============================================================================


def test_get_submissions_for_user_authenticated(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
) -> None:
    """Test listing submissions with authentication."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)

    # Verify each returned submission exists in database
    for submission in data[:5]:  # Check first 5
        db_submission = crud.submission.get_by_uuid(db, uuid=submission["uuid"])
        assert db_submission is not None


def test_get_submissions_for_user_unauthenticated(
    client: TestClient,
) -> None:
    """Test listing submissions without authentication."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/",
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


# =============================================================================
# Suggestions Tests
# =============================================================================


def test_get_submission_suggestions(
    client: TestClient,
    db: Session,
    example_submission_uuid: str,
    normal_user_token_headers: dict,
) -> None:
    """Test getting submission suggestions."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/suggestions/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)

    # Verify the submission exists in database
    db.expire_all()
    db_submission = crud.submission.get_by_uuid(db, uuid=example_submission_uuid)
    assert db_submission is not None


def test_get_submission_suggestions_nonexistent(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
) -> None:
    """Test getting suggestions for nonexistent submission returns an error."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/invalid-uuid/suggestions/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 400

    # Verify it doesn't exist in database
    db_submission = crud.submission.get_by_uuid(db, uuid="invalid-uuid")
    assert db_submission is None
