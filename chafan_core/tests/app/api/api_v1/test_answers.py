from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.config import settings
from chafan_core.tests.conftest import ensure_user_in_site, ensure_user_has_coins
from chafan_core.tests.utils.utils import random_lower_string
from chafan_core.utils.base import get_uuid


# =============================================================================
# CREATE Answer Tests
# =============================================================================


def test_create_answer_unauthenticated(
    client: TestClient,
    normal_user_authored_question_uuid: str,
) -> None:
    """Test that unauthenticated users cannot create answers."""
    data = {
        "question_uuid": normal_user_authored_question_uuid,
        "content": {
            "source": "test answer",
            "rendered_text": "test answer",
            "editor": "markdown",
        },
        "is_published": True,
        "is_autosaved": False,
        "visibility": "anyone",
        "writing_session_uuid": get_uuid(),
    }

    r = client.post(
        f"{settings.API_V1_STR}/answers/",
        json=data,
    )
    assert r.status_code == 401


def test_create_answer_success(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_id: int,
    normal_user_authored_question_uuid: str,
) -> None:
    """Test successful answer creation and verify data in PostgreSQL."""
    answer_content = f"This is a test answer {random_lower_string()}"
    data = {
        "question_uuid": normal_user_authored_question_uuid,
        "content": {
            "source": answer_content,
            "rendered_text": answer_content,
            "editor": "markdown",
        },
        "is_published": True,
        "is_autosaved": False,
        "visibility": "anyone",
        "writing_session_uuid": get_uuid(),
    }

    r = client.post(
        f"{settings.API_V1_STR}/answers/",
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
    db_answer = crud.answer.get_by_uuid(db, uuid=created["uuid"])
    assert db_answer is not None, "Answer not found in database"
    assert db_answer.body == answer_content
    assert db_answer.body_text == answer_content
    assert db_answer.editor == "markdown"
    assert db_answer.is_published is True
    assert db_answer.author_id == normal_user_id
    assert db_answer.created_at is not None

    # Verify question relationship
    assert db_answer.question is not None
    assert db_answer.question.uuid == normal_user_authored_question_uuid


def test_create_answer_as_draft(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_authored_question_uuid: str,
) -> None:
    """Test creating an unpublished (draft) answer and verify in PostgreSQL."""
    answer_content = f"Draft answer {random_lower_string()}"
    data = {
        "question_uuid": normal_user_authored_question_uuid,
        "content": {
            "source": answer_content,
            "rendered_text": answer_content,
            "editor": "tiptap",
        },
        "is_published": False,
        "is_autosaved": False,
        "visibility": "anyone",
        "writing_session_uuid": get_uuid(),
    }

    r = client.post(
        f"{settings.API_V1_STR}/answers/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert 200 <= r.status_code < 300, r.text
    created = r.json()
    assert created["is_published"] is False

    # Verify draft status in PostgreSQL
    db.expire_all()
    db_answer = crud.answer.get_by_uuid(db, uuid=created["uuid"])
    assert db_answer is not None
    assert db_answer.is_published is False
    assert db_answer.body == answer_content


def test_create_answer_invalid_question(
    client: TestClient,
    normal_user_token_headers: dict,
) -> None:
    """Test that creating an answer for an invalid question returns an error."""
    data = {
        "question_uuid": "invalid-question-uuid",
        "content": {
            "source": "test answer",
            "rendered_text": "test answer",
            "editor": "markdown",
        },
        "is_published": True,
        "is_autosaved": False,
        "visibility": "anyone",
        "writing_session_uuid": get_uuid(),
    }

    r = client.post(
        f"{settings.API_V1_STR}/answers/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 400


# =============================================================================
# GET Answer Tests
# =============================================================================


def test_get_answer_success(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_authored_question_uuid: str,
) -> None:
    """Test getting an answer and verify data matches PostgreSQL."""
    # First create an answer
    answer_content = f"Answer to get {random_lower_string()}"
    data = {
        "question_uuid": normal_user_authored_question_uuid,
        "content": {
            "source": answer_content,
            "rendered_text": answer_content,
            "editor": "tiptap",
        },
        "is_published": True,
        "is_autosaved": False,
        "visibility": "anyone",
        "writing_session_uuid": get_uuid(),
    }

    r = client.post(
        f"{settings.API_V1_STR}/answers/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    answer_uuid = r.json()["uuid"]

    # Get the answer
    r = client.get(
        f"{settings.API_V1_STR}/answers/{answer_uuid}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    response_data = r.json()
    assert response_data["uuid"] == answer_uuid

    # Verify response matches database
    db.expire_all()
    db_answer = crud.answer.get_by_uuid(db, uuid=answer_uuid)
    assert db_answer is not None
    assert db_answer.body == response_data["content"]["source"]
    assert db_answer.uuid == response_data["uuid"]


def test_get_answer_nonexistent(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
) -> None:
    """Test that getting a nonexistent answer returns an error."""
    r = client.get(
        f"{settings.API_V1_STR}/answers/invalid-uuid",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 400

    # Verify it doesn't exist in database
    db_answer = crud.answer.get_by_uuid(db, uuid="invalid-uuid")
    assert db_answer is None


# =============================================================================
# UPDATE Answer Tests
# =============================================================================


def test_update_answer_as_author(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_authored_question_uuid: str,
) -> None:
    """Test updating an answer as author and verify in PostgreSQL."""
    # First create an answer
    original_content = f"Original answer {random_lower_string()}"
    data = {
        "question_uuid": normal_user_authored_question_uuid,
        "content": {
            "source": original_content,
            "rendered_text": original_content,
            "editor": "tiptap",
        },
        "is_published": True,
        "is_autosaved": False,
        "visibility": "anyone",
        "writing_session_uuid": get_uuid(),
    }

    r = client.post(
        f"{settings.API_V1_STR}/answers/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    answer_uuid = r.json()["uuid"]

    # Verify original content in database
    db.expire_all()
    db_answer_before = crud.answer.get_by_uuid(db, uuid=answer_uuid)
    assert db_answer_before.body == original_content

    # Update the answer
    new_content = f"Updated answer {random_lower_string()}"
    update_data = {
        "updated_content": {
            "source": new_content,
            "rendered_text": new_content,
            "editor": "tiptap",
        },
        "is_draft": False,
        "visibility": "anyone",
    }

    r = client.put(
        f"{settings.API_V1_STR}/answers/{answer_uuid}",
        headers=normal_user_token_headers,
        json=update_data,
    )
    assert r.status_code == 200

    # Verify updated content in PostgreSQL
    db.expire_all()
    db_answer_after = crud.answer.get_by_uuid(db, uuid=answer_uuid)
    assert db_answer_after is not None
    assert db_answer_after.body == new_content
    assert db_answer_after.body_text == new_content

    # Verify an archive was created
    assert len(db_answer_after.archives) >= 1
    archive = db_answer_after.archives[-1]
    assert archive.body == original_content


def test_update_answer_as_non_author(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    moderator_user_token_headers: dict,
    normal_user_authored_question_uuid: str,
) -> None:
    """Test that non-authors cannot update answers."""
    # Create an answer as normal user
    original_content = f"Answer by normal user {random_lower_string()}"
    data = {
        "question_uuid": normal_user_authored_question_uuid,
        "content": {
            "source": original_content,
            "rendered_text": original_content,
            "editor": "tiptap",
        },
        "is_published": True,
        "is_autosaved": False,
        "visibility": "anyone",
        "writing_session_uuid": get_uuid(),
    }

    r = client.post(
        f"{settings.API_V1_STR}/answers/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    answer_uuid = r.json()["uuid"]

    # Try to update as moderator (non-author)
    update_data = {
        "updated_content": {
            "source": "Unauthorized update",
            "rendered_text": "Unauthorized update",
            "editor": "tiptap",
        },
        "is_draft": False,
        "visibility": "anyone",
    }

    r = client.put(
        f"{settings.API_V1_STR}/answers/{answer_uuid}",
        headers=moderator_user_token_headers,
        json=update_data,
    )
    assert r.status_code == 400

    # Verify data was NOT changed in PostgreSQL
    db.expire_all()
    db_answer = crud.answer.get_by_uuid(db, uuid=answer_uuid)
    assert db_answer.body == original_content


# =============================================================================
# DELETE Answer Tests
# =============================================================================


def test_delete_answer_success(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_authored_question_uuid: str,
) -> None:
    """Test deleting an answer and verify in PostgreSQL."""
    # Create an answer to delete
    data = {
        "question_uuid": normal_user_authored_question_uuid,
        "content": {
            "source": "Answer to delete",
            "rendered_text": "Answer to delete",
            "editor": "tiptap",
        },
        "is_published": True,
        "is_autosaved": False,
        "visibility": "anyone",
        "writing_session_uuid": get_uuid(),
    }

    r = client.post(
        f"{settings.API_V1_STR}/answers/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    answer_uuid = r.json()["uuid"]

    # Verify it exists
    db.expire_all()
    db_answer = crud.answer.get_by_uuid(db, uuid=answer_uuid)
    assert db_answer is not None
    assert db_answer.is_deleted is False

    # Delete it
    r = client.delete(
        f"{settings.API_V1_STR}/answers/{answer_uuid}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200

    # Verify it's marked as deleted in PostgreSQL
    db.expire_all()
    db_answer = crud.answer.get_by_uuid(db, uuid=answer_uuid)
    assert db_answer is not None
    assert db_answer.is_deleted is True
