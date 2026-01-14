from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.config import settings
from chafan_core.tests.utils.utils import random_lower_string


# =============================================================================
# CREATE Comment Tests
# =============================================================================


def test_create_comment_unauthenticated(
    client: TestClient,
    normal_user_authored_question_uuid: str,
    example_site_uuid: str,
) -> None:
    """Test that unauthenticated users cannot create comments."""
    data = {
        "site_uuid": example_site_uuid,
        "question_uuid": normal_user_authored_question_uuid,
        "content": {
            "source": "test comment",
            "rendered_text": "test comment",
            "editor": "wysiwyg",
        },
    }

    r = client.post(
        f"{settings.API_V1_STR}/comments/",
        json=data,
    )
    assert r.status_code == 401


def test_create_comment_validation_error(
    client: TestClient,
    normal_user_token_headers: dict,
    normal_user_authored_question_uuid: str,
    example_site_uuid: str,
) -> None:
    """Test that malformed requests return validation error."""
    r = client.post(
        f"{settings.API_V1_STR}/comments/",
        headers=normal_user_token_headers,
        json={
            "site_uuid": example_site_uuid,
            "question_uuid": normal_user_authored_question_uuid,
            "content": {
                "source": "test comment",
                "rendered_text": "test comment",
                # Missing editor field
            },
        },
    )
    assert r.status_code == 422


def test_create_comment_success(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_id: int,
    normal_user_authored_question_uuid: str,
    example_site_uuid: str,
) -> None:
    """Test successful comment creation and verify data in PostgreSQL."""
    comment_content = f"Test comment {random_lower_string()}"
    data = {
        "site_uuid": example_site_uuid,
        "question_uuid": normal_user_authored_question_uuid,
        "content": {
            "source": comment_content,
            "rendered_text": comment_content,
            "editor": "wysiwyg",
        },
    }

    r = client.post(
        f"{settings.API_V1_STR}/comments/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert 200 <= r.status_code < 300, r.text
    created = r.json()
    assert "author" in created
    assert "uuid" in created

    normal_user_uuid = client.get(
        f"{settings.API_V1_STR}/me", headers=normal_user_token_headers
    ).json()["uuid"]
    assert created["author"]["uuid"] == normal_user_uuid

    # Verify data is stored correctly in PostgreSQL
    db.expire_all()
    db_comment = crud.comment.get_by_uuid(db, uuid=created["uuid"])
    assert db_comment is not None, "Comment not found in database"
    assert db_comment.body == comment_content
    assert db_comment.editor == "wysiwyg"
    assert db_comment.author_id == normal_user_id
    assert db_comment.created_at is not None

    # Verify site relationship
    site = crud.site.get_by_uuid(db, uuid=example_site_uuid)
    assert site is not None
    assert db_comment.site_id == site.id


# =============================================================================
# GET Comment Tests
# =============================================================================


def test_get_comment_success(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_authored_question_uuid: str,
    example_site_uuid: str,
) -> None:
    """Test getting a comment and verify data matches PostgreSQL."""
    # First create a comment
    comment_content = f"Comment to get {random_lower_string()}"
    data = {
        "site_uuid": example_site_uuid,
        "question_uuid": normal_user_authored_question_uuid,
        "content": {
            "source": comment_content,
            "rendered_text": comment_content,
            "editor": "wysiwyg",
        },
    }

    r = client.post(
        f"{settings.API_V1_STR}/comments/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    comment_uuid = r.json()["uuid"]

    # Get the comment
    params = {
        "site_uuid": example_site_uuid,
        "question_uuid": normal_user_authored_question_uuid,
    }
    r = client.get(
        f"{settings.API_V1_STR}/comments/{comment_uuid}",
        headers=normal_user_token_headers,
        params=params,
    )
    assert r.status_code == 200
    response_data = r.json()
    assert response_data["uuid"] == comment_uuid

    # Verify response matches database
    db.expire_all()
    db_comment = crud.comment.get_by_uuid(db, uuid=comment_uuid)
    assert db_comment is not None
    assert db_comment.body == response_data["content"]["source"]
    assert db_comment.uuid == response_data["uuid"]


def test_get_comment_nonexistent(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
) -> None:
    """Test that getting a nonexistent comment returns an error."""
    r = client.get(
        f"{settings.API_V1_STR}/comments/invalid-uuid",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 400

    # Verify it doesn't exist in database
    db_comment = crud.comment.get_by_uuid(db, uuid="invalid-uuid")
    assert db_comment is None


# =============================================================================
# UPDATE Comment Tests
# =============================================================================


def test_update_comment_as_author(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_authored_question_uuid: str,
    example_site_uuid: str,
) -> None:
    """Test updating a comment as author and verify in PostgreSQL."""
    # First create a comment
    original_content = f"Original comment {random_lower_string()}"
    data = {
        "site_uuid": example_site_uuid,
        "question_uuid": normal_user_authored_question_uuid,
        "content": {
            "source": original_content,
            "rendered_text": original_content,
            "editor": "wysiwyg",
        },
    }

    r = client.post(
        f"{settings.API_V1_STR}/comments/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    comment_uuid = r.json()["uuid"]

    # Verify original content in database
    db.expire_all()
    db_comment_before = crud.comment.get_by_uuid(db, uuid=comment_uuid)
    assert db_comment_before.body == original_content

    # Update the comment
    new_content = f"Updated comment {random_lower_string()}"
    r = client.put(
        f"{settings.API_V1_STR}/comments/{comment_uuid}",
        headers=normal_user_token_headers,
        json={"body": new_content},
    )
    assert r.status_code == 200

    # Verify updated content in PostgreSQL
    db.expire_all()
    db_comment_after = crud.comment.get_by_uuid(db, uuid=comment_uuid)
    assert db_comment_after is not None
    assert db_comment_after.body == new_content
    assert db_comment_after.updated_at is not None


def test_update_comment_as_non_author(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    moderator_user_token_headers: dict,
    normal_user_authored_question_uuid: str,
    example_site_uuid: str,
) -> None:
    """Test that non-authors cannot update comments."""
    # Create a comment as normal user
    original_content = f"Comment by normal user {random_lower_string()}"
    data = {
        "site_uuid": example_site_uuid,
        "question_uuid": normal_user_authored_question_uuid,
        "content": {
            "source": original_content,
            "rendered_text": original_content,
            "editor": "wysiwyg",
        },
    }

    r = client.post(
        f"{settings.API_V1_STR}/comments/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    comment_uuid = r.json()["uuid"]

    # Try to update as moderator (non-author)
    r = client.put(
        f"{settings.API_V1_STR}/comments/{comment_uuid}",
        headers=moderator_user_token_headers,
        json={"body": "Unauthorized update"},
    )
    assert r.status_code == 400

    # Verify data was NOT changed in PostgreSQL
    db.expire_all()
    db_comment = crud.comment.get_by_uuid(db, uuid=comment_uuid)
    assert db_comment.body == original_content


def test_update_comment_nonexistent(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
) -> None:
    """Test that updating a nonexistent comment returns an error."""
    r = client.put(
        f"{settings.API_V1_STR}/comments/invalid-uuid",
        headers=normal_user_token_headers,
        json={"body": "Updated content"},
    )
    assert r.status_code == 400

    # Verify it doesn't exist in database
    db_comment = crud.comment.get_by_uuid(db, uuid="invalid-uuid")
    assert db_comment is None


# =============================================================================
# DELETE Comment Tests
# =============================================================================


def test_delete_comment_success(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_authored_question_uuid: str,
    example_site_uuid: str,
) -> None:
    """Test deleting a comment and verify in PostgreSQL."""
    # Create a comment to delete
    data = {
        "site_uuid": example_site_uuid,
        "question_uuid": normal_user_authored_question_uuid,
        "content": {
            "source": "Comment to delete",
            "rendered_text": "Comment to delete",
            "editor": "wysiwyg",
        },
    }

    r = client.post(
        f"{settings.API_V1_STR}/comments/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    comment_uuid = r.json()["uuid"]

    # Verify it exists
    db.expire_all()
    db_comment = crud.comment.get_by_uuid(db, uuid=comment_uuid)
    assert db_comment is not None

    # Delete it
    r = client.delete(
        f"{settings.API_V1_STR}/comments/{comment_uuid}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200

    # Verify it's deleted from PostgreSQL (or marked as deleted)
    db.expire_all()
    db_comment = crud.comment.get_by_uuid(db, uuid=comment_uuid)
    # Comment might be hard deleted or soft deleted depending on implementation
    # If soft delete, check is_deleted flag; if hard delete, it should be None
    if db_comment is not None:
        assert db_comment.is_deleted is True


def test_delete_comment_unauthorized(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    moderator_user_token_headers: dict,
    normal_user_authored_question_uuid: str,
    example_site_uuid: str,
) -> None:
    """Test that non-authors cannot delete comments."""
    # Create a comment as normal user
    original_content = f"Comment by normal user {random_lower_string()}"
    data = {
        "site_uuid": example_site_uuid,
        "question_uuid": normal_user_authored_question_uuid,
        "content": {
            "source": original_content,
            "rendered_text": original_content,
            "editor": "wysiwyg",
        },
    }

    r = client.post(
        f"{settings.API_V1_STR}/comments/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    comment_uuid = r.json()["uuid"]

    # Try to delete as moderator (non-author)
    r = client.delete(
        f"{settings.API_V1_STR}/comments/{comment_uuid}",
        headers=moderator_user_token_headers,
    )
    assert r.status_code == 400

    # Verify comment still exists in PostgreSQL
    db.expire_all()
    db_comment = crud.comment.get_by_uuid(db, uuid=comment_uuid)
    assert db_comment is not None
    assert db_comment.body == original_content
