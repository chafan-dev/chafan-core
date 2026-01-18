import asyncio
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.models.feedback import Feedback
from chafan_core.app.schemas.user import UserCreate
from chafan_core.tests.utils.utils import (
    random_email,
    random_password,
    random_short_lower_string,
)


def _create_test_user(db: Session):
    """Helper to create a test user."""
    user_in = UserCreate(
        email=random_email(),
        password=random_password(),
        handle=random_short_lower_string(),
    )
    return asyncio.run(crud.user.create(db, obj_in=user_in))


def _create_feedback_directly(
    db: Session, description: str, status: str = "sent", user_id: int = None
):
    """Helper to create a feedback directly in the database."""
    import datetime

    feedback = Feedback(
        description=description,
        status=status,
        user_id=user_id,
        created_at=datetime.datetime.now(tz=datetime.timezone.utc),
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def test_get_feedback_by_id(db: Session) -> None:
    """Test getting a feedback by ID."""
    user = _create_test_user(db)
    feedback = _create_feedback_directly(
        db, description="Test feedback", user_id=user.id
    )

    retrieved = crud.feedback.get(db, id=feedback.id)
    assert retrieved is not None
    assert retrieved.id == feedback.id
    assert retrieved.description == "Test feedback"


def test_get_feedback_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent feedback."""
    result = crud.feedback.get(db, id=99999999)
    assert result is None


def test_feedback_with_different_statuses(db: Session) -> None:
    """Test creating feedback with different statuses."""
    user = _create_test_user(db)

    statuses = ["sent", "in_progress", "done", "wont_fix"]

    for status in statuses:
        feedback = _create_feedback_directly(
            db,
            description=f"Feedback with status {status}",
            status=status,
            user_id=user.id,
        )

        retrieved = crud.feedback.get(db, id=feedback.id)
        assert retrieved is not None
        assert retrieved.status == status


def test_feedback_timestamps(db: Session) -> None:
    """Test that feedback has correct timestamps."""
    import datetime

    user = _create_test_user(db)

    before_create = datetime.datetime.now(tz=datetime.timezone.utc)

    feedback = _create_feedback_directly(
        db, description="Timestamp test", user_id=user.id
    )

    after_create = datetime.datetime.now(tz=datetime.timezone.utc)

    assert feedback.created_at is not None
    assert before_create <= feedback.created_at <= after_create


def test_get_multi_feedback(db: Session) -> None:
    """Test getting multiple feedback entries."""
    user = _create_test_user(db)

    # Create several feedback entries
    for i in range(5):
        _create_feedback_directly(db, description=f"Feedback {i}", user_id=user.id)

    feedbacks = crud.feedback.get_multi(db, skip=0, limit=10)
    assert len(feedbacks) >= 5


def test_feedback_without_user(db: Session) -> None:
    """Test creating feedback without an associated user."""
    feedback = _create_feedback_directly(
        db, description="Anonymous feedback", user_id=None
    )

    retrieved = crud.feedback.get(db, id=feedback.id)
    assert retrieved is not None
    assert retrieved.user_id is None


def test_update_feedback_status(db: Session) -> None:
    """Test updating feedback status."""
    user = _create_test_user(db)
    feedback = _create_feedback_directly(
        db, description="To be updated", status="sent", user_id=user.id
    )

    assert feedback.status == "sent"

    updated = crud.feedback.update(db, db_obj=feedback, obj_in={"status": "done"})

    assert updated.status == "done"


def test_multiple_feedback_from_same_user(db: Session) -> None:
    """Test that a user can submit multiple feedback entries."""
    user = _create_test_user(db)

    feedbacks = []
    for i in range(3):
        feedback = _create_feedback_directly(
            db, description=f"User feedback {i}", user_id=user.id
        )
        feedbacks.append(feedback)

    assert len(feedbacks) == 3
    assert all(f.user_id == user.id for f in feedbacks)


def test_feedback_with_location_url(db: Session) -> None:
    """Test creating feedback with a location URL."""
    import datetime

    user = _create_test_user(db)

    feedback = Feedback(
        description="Bug on specific page",
        status="sent",
        user_id=user.id,
        location_url="https://example.com/buggy-page",
        created_at=datetime.datetime.now(tz=datetime.timezone.utc),
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    retrieved = crud.feedback.get(db, id=feedback.id)
    assert retrieved is not None
    assert retrieved.location_url == "https://example.com/buggy-page"
