"""
Tests for submissions endpoints.

This test file aims to achieve high coverage for:
chafan_core/app/api/api_v1/endpoints/submissions.py

Coverage Progress:
- Phase 1 (Simple reads): [ ] get_submission_upvotes, [ ] bump_views_counter, [ ] get_submission
- Phase 2 (CRUD): [ ] create_submission, [ ] update_submission, [ ] get_submission_archives
- Phase 3 (Interactions): [ ] upvote_submission, [ ] cancel_upvote, [ ] hide_submission
- Phase 4 (Advanced): [ ] get_submissions_for_user, [ ] get_submission_suggestions
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.config import settings
from chafan_core.tests.utils.utils import random_lower_string


# =============================================================================
# PHASE 1: Simple Read Operations
# =============================================================================


def test_get_submission_upvotes_unauthenticated(
    client: TestClient,
    example_submission_uuid: str,
) -> None:
    """Test getting submission upvotes without authentication."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/"
    )
    assert r.status_code == 200
    data = r.json()
    assert "count" in data
    assert "upvoted" in data
    assert data["upvoted"] is False  # Not logged in
    assert "submission_uuid" in data


def test_get_submission_upvotes_authenticated(
    client: TestClient,
    example_submission_uuid: str,
    normal_user_token_headers: dict,
) -> None:
    """Test getting submission upvotes with authentication."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "count" in data
    assert "upvoted" in data
    assert data["submission_uuid"] == example_submission_uuid


def test_get_submission_upvotes_nonexistent(
    client: TestClient,
) -> None:
    """Test getting upvotes for non-existent submission."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/invalid-uuid/upvotes/"
    )
    assert r.status_code == 400
    assert "doesn't exists" in r.json()["detail"]


def test_bump_views_counter(
    client: TestClient,
    example_submission_uuid: str,
) -> None:
    """Test incrementing submission view counter."""
    r = client.post(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/views/"
    )
    assert r.status_code == 200


def test_bump_views_counter_nonexistent(
    client: TestClient,
) -> None:
    """Test view counter for non-existent submission."""
    r = client.post(
        f"{settings.API_V1_STR}/submissions/invalid-uuid/views/"
    )
    assert r.status_code == 400


def test_get_submission_authenticated(
    client: TestClient,
    example_submission_uuid: str,
    normal_user_token_headers: dict,
) -> None:
    """Test retrieving an existing submission."""
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


def test_get_submission_nonexistent(
    client: TestClient,
    normal_user_token_headers: dict,
) -> None:
    """Test retrieving a non-existent submission."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/invalid-uuid",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 400
    assert "doesn't exists" in r.json()["detail"]


# =============================================================================
# PHASE 2: CRUD Operations
# =============================================================================


def test_create_submission_unauthenticated(
    client: TestClient,
    example_site_uuid: str,
) -> None:
    """Test creating submission without authentication."""
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
    normal_user_token_headers: dict,
) -> None:
    """Test creating submission with invalid site UUID."""
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


def test_create_submission_success(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_uuid: str,
    normal_user_id: int,
    example_site_uuid: str,
    superuser_token_headers: dict,
) -> None:
    """Test successful submission creation."""
    # Ensure user is member of the site
    site = crud.site.get_by_uuid(db, uuid=example_site_uuid)
    assert site is not None
    profile = crud.profile.get_by_user_and_site(
        db, owner_id=normal_user_id, site_id=site.id
    )
    if not profile:
        r = client.post(
            f"{settings.API_V1_STR}/users/invite",
            headers=superuser_token_headers,
            json={"site_uuid": example_site_uuid, "user_uuid": normal_user_uuid},
        )
        r.raise_for_status()

    # Create submission
    data = {
        "site_uuid": example_site_uuid,
        "title": f"Test Submission {random_lower_string()}",
        "url": "https://example.com/test",
    }
    r = client.post(
        f"{settings.API_V1_STR}/submissions/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert 200 <= r.status_code < 300, r.text
    created = r.json()
    assert "uuid" in created
    assert created["title"] == data["title"]
    assert created["url"] == data["url"]
    assert created["author"]["uuid"] == normal_user_uuid


def test_update_submission_as_author(
    client: TestClient,
    example_submission_uuid: str,
    normal_user_token_headers: dict,
) -> None:
    """Test author can update their submission."""
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


def test_update_submission_as_non_author(
    client: TestClient,
    example_submission_uuid: str,
    moderator_user_token_headers: dict,
) -> None:
    """Test non-author cannot update submission."""
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


def test_update_submission_nonexistent(
    client: TestClient,
    normal_user_token_headers: dict,
) -> None:
    """Test updating non-existent submission."""
    data = {
        "title": "Updated Title",
    }
    r = client.put(
        f"{settings.API_V1_STR}/submissions/invalid-uuid",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 400


def test_get_submission_archives(
    client: TestClient,
    example_submission_uuid: str,
    normal_user_token_headers: dict,
) -> None:
    """Test getting submission archives."""
    # First update to create an archive
    client.put(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}",
        headers=normal_user_token_headers,
        json={"title": f"Updated {random_lower_string()}"},
    )

    # Get archives
    r = client.get(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/archives/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    archives = r.json()
    assert isinstance(archives, list)


def test_get_submission_archives_nonexistent(
    client: TestClient,
    normal_user_token_headers: dict,
) -> None:
    """Test getting archives for non-existent submission."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/invalid-uuid/archives/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 400


# =============================================================================
# PHASE 3: User Interactions
# =============================================================================


def test_upvote_submission_success(
    client: TestClient,
    example_submission_uuid: str,
    moderator_user_token_headers: dict,
) -> None:
    """Test upvoting a submission."""
    # Get initial count
    r = client.get(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/"
    )
    initial_count = r.json()["count"]

    # Upvote
    r = client.post(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/",
        headers=moderator_user_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["upvoted"] is True
    assert data["count"] >= initial_count


def test_upvote_submission_idempotent(
    client: TestClient,
    example_submission_uuid: str,
    moderator_user_token_headers: dict,
) -> None:
    """Test upvoting same submission twice is idempotent."""
    # First upvote
    r1 = client.post(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/",
        headers=moderator_user_token_headers,
    )
    count1 = r1.json()["count"]

    # Second upvote (should not increase count)
    r2 = client.post(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/",
        headers=moderator_user_token_headers,
    )
    count2 = r2.json()["count"]

    assert count1 == count2


def test_upvote_submission_author_cannot_upvote(
    client: TestClient,
    example_submission_uuid: str,
    normal_user_token_headers: dict,
) -> None:
    """Test author cannot upvote their own submission."""
    r = client.post(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 400
    assert "Author can't upvote" in r.json()["detail"]


def test_cancel_upvote_submission(
    client: TestClient,
    example_submission_uuid: str,
    moderator_user_token_headers: dict,
) -> None:
    """Test canceling an upvote."""
    # First upvote
    r = client.post(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/",
        headers=moderator_user_token_headers,
    )
    upvote_count = r.json()["count"]

    # Cancel upvote
    r = client.delete(
        f"{settings.API_V1_STR}/submissions/{example_submission_uuid}/upvotes/",
        headers=moderator_user_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["upvoted"] is False
    assert data["count"] <= upvote_count


def test_hide_submission_as_author(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_uuid: str,
    normal_user_id: int,
    example_site_uuid: str,
    superuser_token_headers: dict,
) -> None:
    """Test author can hide their submission."""
    # Create a new submission for this test
    site = crud.site.get_by_uuid(db, uuid=example_site_uuid)
    assert site is not None
    profile = crud.profile.get_by_user_and_site(
        db, owner_id=normal_user_id, site_id=site.id
    )
    if not profile:
        r = client.post(
            f"{settings.API_V1_STR}/users/invite",
            headers=superuser_token_headers,
            json={"site_uuid": example_site_uuid, "user_uuid": normal_user_uuid},
        )
        r.raise_for_status()

    r = client.post(
        f"{settings.API_V1_STR}/submissions/",
        headers=normal_user_token_headers,
        json={
            "site_uuid": example_site_uuid,
            "title": f"To Hide {random_lower_string()}",
            "url": "https://example.com/hide-test",
        },
    )
    submission_uuid = r.json()["uuid"]

    # Hide it
    r = client.put(
        f"{settings.API_V1_STR}/submissions/{submission_uuid}/hide",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["is_hidden"] is True


# =============================================================================
# PHASE 4: Advanced Features
# =============================================================================


def test_get_submissions_for_user_authenticated(
    client: TestClient,
    normal_user_token_headers: dict,
) -> None:
    """Test getting submissions list for authenticated user."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_get_submissions_for_user_unauthenticated(
    client: TestClient,
) -> None:
    """Test getting submissions list for visitor."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/",
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_get_submission_suggestions(
    client: TestClient,
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


def test_get_submission_suggestions_nonexistent(
    client: TestClient,
    normal_user_token_headers: dict,
) -> None:
    """Test getting suggestions for non-existent submission."""
    r = client.get(
        f"{settings.API_V1_STR}/submissions/invalid-uuid/suggestions/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 400
