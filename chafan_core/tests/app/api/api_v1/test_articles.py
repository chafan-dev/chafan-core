from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.config import settings
from chafan_core.tests.conftest import ensure_user_has_coins
from chafan_core.utils.base import get_uuid


# =============================================================================
# GET Article Tests
# =============================================================================


def test_get_article_unauthenticated(
    client: TestClient,
    db: Session,
    example_article_uuid: str,
) -> None:
    """Test that unauthenticated users can get a published article."""
    r = client.get(f"{settings.API_V1_STR}/articles/{example_article_uuid}")
    assert r.status_code == 200
    data = r.json()
    assert data["uuid"] == example_article_uuid
    assert "title" in data
    assert "author" in data
    assert "content" in data
    assert "article_column" in data

    # Verify data exists in database
    db.expire_all()
    db_article = crud.article.get_by_uuid(db, uuid=example_article_uuid)
    assert db_article is not None, f"Article {example_article_uuid} not found in database"
    assert db_article.uuid == example_article_uuid
    assert db_article.title == data["title"]
    assert db_article.is_published is True


def test_get_article_authenticated(
    client: TestClient,
    db: Session,
    example_article_uuid: str,
    normal_user_token_headers: dict,
) -> None:
    """Test that authenticated users can get an article with full details."""
    r = client.get(
        f"{settings.API_V1_STR}/articles/{example_article_uuid}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["uuid"] == example_article_uuid
    assert "title" in data
    assert "author" in data
    assert "content" in data
    assert "upvoted" in data
    assert "view_times" in data

    # Verify data in database matches response
    db.expire_all()
    db_article = crud.article.get_by_uuid(db, uuid=example_article_uuid)
    assert db_article is not None, f"Article {example_article_uuid} not found in database"
    assert db_article.title == data["title"]
    assert db_article.body == data["content"]["source"]


def test_get_article_nonexistent(
    client: TestClient,
    db: Session,
) -> None:
    """Test that getting a nonexistent article returns an error."""
    r = client.get(f"{settings.API_V1_STR}/articles/invalid-uuid")
    assert r.status_code == 400
    assert "doesn't exists" in r.json()["detail"]

    # Verify it doesn't exist in database
    db_article = crud.article.get_by_uuid(db, uuid="invalid-uuid")
    assert db_article is None


# =============================================================================
# CREATE Article Tests
# =============================================================================


def test_create_article_unauthenticated(
    client: TestClient,
    example_article_column_uuid: str,
) -> None:
    """Test that unauthenticated users cannot create articles."""
    data = {
        "title": "Unauthorized Article",
        "content": {"source": "Content", "editor": "tiptap"},
        "article_column_uuid": example_article_column_uuid,
        "is_published": True,
        "writing_session_uuid": get_uuid(),
        "visibility": "anyone",
    }
    r = client.post(f"{settings.API_V1_STR}/articles/", json=data)
    assert r.status_code == 401


def test_create_article_invalid_column(
    client: TestClient,
    normal_user_token_headers: dict,
) -> None:
    """Test that creating an article with an invalid column returns an error."""
    data = {
        "title": "Test Article",
        "content": {"source": "Content", "editor": "tiptap"},
        "article_column_uuid": "invalid-uuid",
        "is_published": True,
        "writing_session_uuid": get_uuid(),
        "visibility": "anyone",
    }
    r = client.post(
        f"{settings.API_V1_STR}/articles/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 400
    assert "article column" in r.json()["detail"].lower()


def test_create_article_not_owner_of_column(
    client: TestClient,
    example_article_column_uuid: str,
    moderator_user_token_headers: dict,
) -> None:
    """Test that users cannot create articles in columns they don't own."""
    data = {
        "title": "Unauthorized Column Article",
        "content": {"source": "Content", "editor": "tiptap"},
        "article_column_uuid": example_article_column_uuid,
        "is_published": True,
        "writing_session_uuid": get_uuid(),
        "visibility": "anyone",
    }
    r = client.post(
        f"{settings.API_V1_STR}/articles/",
        headers=moderator_user_token_headers,
        json=data,
    )
    assert r.status_code == 400
    assert "not owned by current user" in r.json()["detail"]


def test_create_article_success(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_uuid: str,
    normal_user_id: int,
    example_article_column_uuid: str,
) -> None:
    """Test successful article creation and verify data in PostgreSQL."""
    ensure_user_has_coins(db, normal_user_id, coins=100)

    title = f"New Test Article {get_uuid()}"
    body_content = "This is the article body content for testing."
    data = {
        "title": title,
        "content": {
            "source": body_content,
            "rendered_text": body_content,
            "editor": "tiptap",
        },
        "article_column_uuid": example_article_column_uuid,
        "is_published": True,
        "writing_session_uuid": get_uuid(),
        "visibility": "anyone",
    }
    r = client.post(
        f"{settings.API_V1_STR}/articles/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200, f"Create article failed: {r.json()}"
    created = r.json()
    assert "uuid" in created
    assert created["title"] == title
    assert created["author"]["uuid"] == normal_user_uuid
    assert created["is_published"] is True

    # Verify data is stored correctly in PostgreSQL
    db.expire_all()  # Clear cache to get fresh data
    db_article = crud.article.get_by_uuid(db, uuid=created["uuid"])
    assert db_article is not None, "Article not found in database"
    assert db_article.title == title
    assert db_article.body == body_content
    assert db_article.body_text == body_content
    assert db_article.editor == "tiptap"
    assert db_article.is_published is True
    assert db_article.author_id == normal_user_id
    assert db_article.visibility.value == "anyone"
    assert db_article.created_at is not None
    assert db_article.updated_at is not None

    # Verify article column relationship
    assert db_article.article_column is not None
    assert db_article.article_column.uuid == example_article_column_uuid


def test_create_article_as_draft(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_id: int,
    example_article_column_uuid: str,
) -> None:
    """Test creating an unpublished (draft) article and verify in PostgreSQL."""
    ensure_user_has_coins(db, normal_user_id, coins=100)

    title = f"Draft Article {get_uuid()}"
    body_content = "Draft content for testing"
    data = {
        "title": title,
        "content": {"source": body_content, "editor": "tiptap"},
        "article_column_uuid": example_article_column_uuid,
        "is_published": False,
        "writing_session_uuid": get_uuid(),
        "visibility": "anyone",
    }
    r = client.post(
        f"{settings.API_V1_STR}/articles/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200, f"Create draft article failed: {r.json()}"
    created = r.json()
    assert created["is_published"] is False

    # Verify draft status in PostgreSQL
    db.expire_all()
    db_article = crud.article.get_by_uuid(db, uuid=created["uuid"])
    assert db_article is not None
    assert db_article.is_published is False
    assert db_article.title == title
    assert db_article.body == body_content
    # Draft articles should not have updated_at set
    assert db_article.updated_at is None


# =============================================================================
# UPDATE Article Tests
# =============================================================================


def test_update_article_as_author(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_id: int,
    example_article_column_uuid: str,
) -> None:
    """Test that authors can update their own articles and verify in PostgreSQL."""
    # First create an article to update
    ensure_user_has_coins(db, normal_user_id, coins=100)

    original_title = f"Article to Update {get_uuid()}"
    original_content = "Original content"
    create_data = {
        "title": original_title,
        "content": {
            "source": original_content,
            "rendered_text": original_content,
            "editor": "tiptap",
        },
        "article_column_uuid": example_article_column_uuid,
        "is_published": True,
        "writing_session_uuid": get_uuid(),
        "visibility": "anyone",
    }
    r = client.post(
        f"{settings.API_V1_STR}/articles/",
        headers=normal_user_token_headers,
        json=create_data,
    )
    assert r.status_code == 200
    article_uuid = r.json()["uuid"]

    # Verify original data in database
    db.expire_all()
    db_article_before = crud.article.get_by_uuid(db, uuid=article_uuid)
    assert db_article_before is not None
    assert db_article_before.title == original_title
    original_updated_at = db_article_before.updated_at

    # Now update it
    new_title = f"Updated Title {get_uuid()}"
    new_content = "Updated content for the article"
    update_data = {
        "updated_title": new_title,
        "updated_content": {
            "source": new_content,
            "rendered_text": new_content,
            "editor": "tiptap",
        },
        "is_draft": False,
        "visibility": "anyone",
    }
    r = client.put(
        f"{settings.API_V1_STR}/articles/{article_uuid}",
        headers=normal_user_token_headers,
        json=update_data,
    )
    assert r.status_code == 200, f"Update failed: {r.json()}"
    assert r.json()["title"] == new_title

    # Verify updated data in PostgreSQL
    db.expire_all()
    db_article_after = crud.article.get_by_uuid(db, uuid=article_uuid)
    assert db_article_after is not None
    assert db_article_after.title == new_title
    assert db_article_after.body == new_content
    assert db_article_after.body_text == new_content
    # updated_at should be updated
    assert db_article_after.updated_at is not None
    assert db_article_after.updated_at >= original_updated_at

    # Verify an archive was created for the original content
    assert len(db_article_after.archives) >= 1
    latest_archive = db_article_after.archives[-1]
    assert latest_archive.title == original_title
    assert latest_archive.body == original_content


def test_update_article_as_non_author(
    client: TestClient,
    db: Session,
    example_article_uuid: str,
    moderator_user_token_headers: dict,
) -> None:
    """Test that non-authors cannot update articles they don't own."""
    # Get original data from database
    db.expire_all()
    db_article_before = crud.article.get_by_uuid(db, uuid=example_article_uuid)
    assert db_article_before is not None, f"Article {example_article_uuid} not found"
    original_title = db_article_before.title
    original_body = db_article_before.body

    update_data = {
        "updated_title": "Unauthorized Update",
        "updated_content": {"source": "Unauthorized", "editor": "tiptap"},
        "is_draft": False,
        "visibility": "anyone",
    }
    r = client.put(
        f"{settings.API_V1_STR}/articles/{example_article_uuid}",
        headers=moderator_user_token_headers,
        json=update_data,
    )
    assert r.status_code == 400
    assert "Unauthorized" in r.json()["detail"]

    # Verify data was NOT changed in PostgreSQL
    db.expire_all()
    db_article_after = crud.article.get_by_uuid(db, uuid=example_article_uuid)
    assert db_article_after is not None, f"Article {example_article_uuid} not found"
    assert db_article_after.title == original_title
    assert db_article_after.body == original_body


def test_update_article_nonexistent(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
) -> None:
    """Test that updating a nonexistent article returns an error."""
    update_data = {
        "updated_title": "Update Nonexistent",
        "updated_content": {"source": "Content", "editor": "tiptap"},
        "is_draft": False,
        "visibility": "anyone",
    }
    r = client.put(
        f"{settings.API_V1_STR}/articles/invalid-uuid",
        headers=normal_user_token_headers,
        json=update_data,
    )
    assert r.status_code == 400
    assert "doesn't exists" in r.json()["detail"]

    # Verify it doesn't exist in database
    db_article = crud.article.get_by_uuid(db, uuid="invalid-uuid")
    assert db_article is None


def test_update_article_save_as_draft(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_id: int,
    example_article_column_uuid: str,
) -> None:
    """Test saving article changes as a draft and verify in PostgreSQL."""
    ensure_user_has_coins(db, normal_user_id, coins=100)

    # Create an article first
    original_title = f"Article for Draft Test {get_uuid()}"
    original_content = "Original published content"
    create_data = {
        "title": original_title,
        "content": {
            "source": original_content,
            "rendered_text": original_content,
            "editor": "tiptap",
        },
        "article_column_uuid": example_article_column_uuid,
        "is_published": True,
        "writing_session_uuid": get_uuid(),
        "visibility": "anyone",
    }
    r = client.post(
        f"{settings.API_V1_STR}/articles/",
        headers=normal_user_token_headers,
        json=create_data,
    )
    assert r.status_code == 200
    article_uuid = r.json()["uuid"]

    # Save as draft (shouldn't change the published content)
    draft_title = "Draft Title - Not Published Yet"
    draft_content = "Draft content - should be saved separately"
    update_data = {
        "updated_title": draft_title,
        "updated_content": {"source": draft_content, "editor": "tiptap"},
        "is_draft": True,
        "visibility": "anyone",
    }
    r = client.put(
        f"{settings.API_V1_STR}/articles/{article_uuid}",
        headers=normal_user_token_headers,
        json=update_data,
    )
    assert r.status_code == 200
    # The published title should remain unchanged
    assert r.json()["title"] == original_title

    # Verify in PostgreSQL: published content unchanged, draft content saved
    db.expire_all()
    db_article = crud.article.get_by_uuid(db, uuid=article_uuid)
    assert db_article is not None
    # Published content should be unchanged
    assert db_article.title == original_title
    assert db_article.body == original_content
    # Draft content should be saved
    assert db_article.title_draft == draft_title
    assert db_article.body_draft == draft_content
    assert db_article.draft_saved_at is not None


# =============================================================================
# Views Counter Tests
# =============================================================================


def test_bump_views_counter(
    client: TestClient,
    db: Session,
    example_article_uuid: str,
) -> None:
    """Test that bumping views counter works."""
    r = client.post(f"{settings.API_V1_STR}/articles/{example_article_uuid}/views/")
    assert r.status_code == 200

    # Note: View counts are typically handled asynchronously via Redis,
    # so we just verify the endpoint works without error


def test_bump_views_counter_nonexistent(
    client: TestClient,
) -> None:
    """Test that bumping views for nonexistent article returns an error."""
    r = client.post(f"{settings.API_V1_STR}/articles/invalid-uuid/views/")
    assert r.status_code == 400


# =============================================================================
# Archives Tests
# =============================================================================


def test_get_article_archives(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_id: int,
    example_article_column_uuid: str,
) -> None:
    """Test getting article archives after updates and verify in PostgreSQL."""
    ensure_user_has_coins(db, normal_user_id, coins=100)

    # Create an article
    original_title = f"Article for Archives {get_uuid()}"
    original_content = "Original content for archive test"
    create_data = {
        "title": original_title,
        "content": {
            "source": original_content,
            "rendered_text": original_content,
            "editor": "tiptap",
        },
        "article_column_uuid": example_article_column_uuid,
        "is_published": True,
        "writing_session_uuid": get_uuid(),
        "visibility": "anyone",
    }
    r = client.post(
        f"{settings.API_V1_STR}/articles/",
        headers=normal_user_token_headers,
        json=create_data,
    )
    assert r.status_code == 200
    article_uuid = r.json()["uuid"]

    # Update it to create an archive
    new_title = f"Updated {get_uuid()}"
    new_content = "Updated content - original should be archived"
    update_data = {
        "updated_title": new_title,
        "updated_content": {
            "source": new_content,
            "rendered_text": new_content,
            "editor": "tiptap",
        },
        "is_draft": False,
        "visibility": "anyone",
    }
    r = client.put(
        f"{settings.API_V1_STR}/articles/{article_uuid}",
        headers=normal_user_token_headers,
        json=update_data,
    )
    assert r.status_code == 200

    # Get archives via API
    r = client.get(
        f"{settings.API_V1_STR}/articles/{article_uuid}/archives/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    archives = r.json()
    assert isinstance(archives, list)
    assert len(archives) >= 1

    # Verify archives in PostgreSQL
    db.expire_all()
    db_article = crud.article.get_by_uuid(db, uuid=article_uuid)
    assert db_article is not None
    assert len(db_article.archives) >= 1

    # Check that the archive contains the original content
    archive = db_article.archives[0]
    assert archive.title == original_title
    assert archive.body == original_content
    assert archive.created_at is not None


def test_get_article_archives_nonexistent(
    client: TestClient,
    normal_user_token_headers: dict,
) -> None:
    """Test that getting archives for nonexistent article returns an error."""
    r = client.get(
        f"{settings.API_V1_STR}/articles/invalid-uuid/archives/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 400


def test_get_article_archives_unauthorized(
    client: TestClient,
    db: Session,
    example_article_uuid: str,
    moderator_user_token_headers: dict,
) -> None:
    """Test that non-authors cannot access article archives."""
    r = client.get(
        f"{settings.API_V1_STR}/articles/{example_article_uuid}/archives/",
        headers=moderator_user_token_headers,
    )
    assert r.status_code == 400
    assert "Unauthorized" in r.json()["detail"]

    # Verify the article exists but access is denied (not a data issue)
    db.expire_all()
    db_article = crud.article.get_by_uuid(db, uuid=example_article_uuid)
    assert db_article is not None, f"Article {example_article_uuid} not found in database"


# =============================================================================
# DELETE Article Tests
# =============================================================================


def test_delete_article_success(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_id: int,
    example_article_column_uuid: str,
) -> None:
    """Test deleting an article and verify it's marked as deleted in PostgreSQL."""
    ensure_user_has_coins(db, normal_user_id, coins=100)

    # Create an article to delete
    title = f"Article to Delete {get_uuid()}"
    create_data = {
        "title": title,
        "content": {"source": "Content to delete", "editor": "tiptap"},
        "article_column_uuid": example_article_column_uuid,
        "is_published": True,
        "writing_session_uuid": get_uuid(),
        "visibility": "anyone",
    }
    r = client.post(
        f"{settings.API_V1_STR}/articles/",
        headers=normal_user_token_headers,
        json=create_data,
    )
    assert r.status_code == 200
    article_uuid = r.json()["uuid"]

    # Verify it exists
    db.expire_all()
    db_article = crud.article.get_by_uuid(db, uuid=article_uuid)
    assert db_article is not None
    assert db_article.is_deleted is False

    # Delete it
    r = client.delete(
        f"{settings.API_V1_STR}/articles/{article_uuid}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200

    # Verify it's marked as deleted in PostgreSQL
    db.expire_all()
    db_article = crud.article.get_by_uuid(db, uuid=article_uuid)
    assert db_article is not None
    assert db_article.is_deleted is True
    assert db_article.body == "[DELETED]"


def test_delete_article_unauthorized(
    client: TestClient,
    db: Session,
    example_article_uuid: str,
    moderator_user_token_headers: dict,
) -> None:
    """Test that non-authors cannot delete articles."""
    # Verify article exists and is not deleted
    db.expire_all()
    db_article_before = crud.article.get_by_uuid(db, uuid=example_article_uuid)
    assert db_article_before is not None, f"Article {example_article_uuid} not found in database"
    assert db_article_before.is_deleted is False

    r = client.delete(
        f"{settings.API_V1_STR}/articles/{example_article_uuid}",
        headers=moderator_user_token_headers,
    )
    assert r.status_code == 400
    assert "Unauthorized" in r.json()["detail"]

    # Verify article is NOT deleted in PostgreSQL
    db.expire_all()
    db_article_after = crud.article.get_by_uuid(db, uuid=example_article_uuid)
    assert db_article_after is not None
    assert db_article_after.is_deleted is False


def test_delete_article_nonexistent(
    client: TestClient,
    normal_user_token_headers: dict,
) -> None:
    """Test that deleting a nonexistent article returns an error."""
    r = client.delete(
        f"{settings.API_V1_STR}/articles/invalid-uuid",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 400
    assert "doesn't exists" in r.json()["detail"]
