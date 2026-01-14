from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from chafan_core.app.config import settings
from chafan_core.tests.conftest import ensure_user_has_coins
from chafan_core.utils.base import get_uuid


# =============================================================================
# GET Article Tests
# =============================================================================


def test_get_article_unauthenticated(
    client: TestClient,
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


def test_get_article_authenticated(
    client: TestClient,
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


def test_get_article_nonexistent(
    client: TestClient,
) -> None:
    """Test that getting a nonexistent article returns an error."""
    r = client.get(f"{settings.API_V1_STR}/articles/invalid-uuid")
    assert r.status_code == 400
    assert "doesn't exists" in r.json()["detail"]


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
    """Test successful article creation."""
    ensure_user_has_coins(db, normal_user_id, coins=100)

    title = f"New Test Article {get_uuid()}"
    data = {
        "title": title,
        "content": {
            "source": "This is the article body content.",
            "rendered_text": "This is the article body content.",
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


def test_create_article_as_draft(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_id: int,
    example_article_column_uuid: str,
) -> None:
    """Test creating an unpublished (draft) article."""
    ensure_user_has_coins(db, normal_user_id, coins=100)

    title = f"Draft Article {get_uuid()}"
    data = {
        "title": title,
        "content": {"source": "Draft content", "editor": "tiptap"},
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
    """Test that authors can update their own articles."""
    # First create an article to update
    ensure_user_has_coins(db, normal_user_id, coins=100)

    create_data = {
        "title": f"Article to Update {get_uuid()}",
        "content": {"source": "Original content", "editor": "tiptap"},
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

    # Now update it
    new_title = f"Updated Title {get_uuid()}"
    update_data = {
        "updated_title": new_title,
        "updated_content": {
            "source": "Updated content",
            "rendered_text": "Updated content",
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


def test_update_article_as_non_author(
    client: TestClient,
    example_article_uuid: str,
    moderator_user_token_headers: dict,
) -> None:
    """Test that non-authors cannot update articles they don't own."""
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


def test_update_article_nonexistent(
    client: TestClient,
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


def test_update_article_save_as_draft(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_id: int,
    example_article_column_uuid: str,
) -> None:
    """Test saving article changes as a draft without publishing."""
    ensure_user_has_coins(db, normal_user_id, coins=100)

    # Create an article first
    create_data = {
        "title": f"Article for Draft Test {get_uuid()}",
        "content": {"source": "Original", "editor": "tiptap"},
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
    original_title = r.json()["title"]

    # Save as draft (shouldn't change the published title)
    update_data = {
        "updated_title": "Draft Title",
        "updated_content": {"source": "Draft content", "editor": "tiptap"},
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


# =============================================================================
# Views Counter Tests
# =============================================================================


def test_bump_views_counter(
    client: TestClient,
    example_article_uuid: str,
) -> None:
    """Test that bumping views counter works."""
    r = client.post(f"{settings.API_V1_STR}/articles/{example_article_uuid}/views/")
    assert r.status_code == 200


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
    """Test getting article archives after updates."""
    ensure_user_has_coins(db, normal_user_id, coins=100)

    # Create an article
    create_data = {
        "title": f"Article for Archives {get_uuid()}",
        "content": {
            "source": "Original content",
            "rendered_text": "Original content",
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
    update_data = {
        "updated_title": f"Updated {get_uuid()}",
        "updated_content": {
            "source": "Updated content",
            "rendered_text": "Updated content",
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

    # Get archives
    r = client.get(
        f"{settings.API_V1_STR}/articles/{article_uuid}/archives/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    archives = r.json()
    assert isinstance(archives, list)
    assert len(archives) >= 1


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
