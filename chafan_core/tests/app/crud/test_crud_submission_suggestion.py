import asyncio
import datetime
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.submission_suggestion import (
    SubmissionSuggestionCreate,
    SubmissionSuggestionUpdate,
)
from chafan_core.app.schemas.submission import SubmissionCreate
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.schemas.user import UserCreate
from chafan_core.app.schemas.site import SiteCreate
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


def _create_test_site(db: Session, moderator):
    """Helper to create a test site."""
    site_in = SiteCreate(
        name=f"Test Site {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
        description="Test site",
        permission_type="private",
    )
    return crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=None
    )


def _create_test_submission(db: Session, author_id: int, site):
    """Helper to create a test submission."""
    submission_in = SubmissionCreate(
        site_uuid=site.uuid,
        title=f"Test Submission {random_short_lower_string()}",
        url="https://example.com/test",
    )
    return crud.submission.create_with_author(db, obj_in=submission_in, author_id=author_id)


def test_create_submission_suggestion_with_author(db: Session) -> None:
    """Test creating a submission suggestion with an author."""
    moderator = _create_test_user(db)
    submission_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    submission = _create_test_submission(db, author_id=submission_author.id, site=site)

    suggestion_in = SubmissionSuggestionCreate(
        submission_uuid=submission.uuid,
        title="Improved Title",
        desc=RichText(
            source="Better description",
            rendered_text="Better description",
            editor="tiptap",
        ),
        comment="Fixed the title and description",
    )

    suggestion = crud.submission_suggestion.create_with_author(
        db, obj_in=suggestion_in, author_id=suggester.id, submission=submission
    )

    assert suggestion is not None
    assert suggestion.author_id == suggester.id
    assert suggestion.submission_id == submission.id
    assert suggestion.status == "pending"
    assert suggestion.title == "Improved Title"
    assert suggestion.comment == "Fixed the title and description"
    assert suggestion.uuid is not None
    assert suggestion.created_at is not None


def test_create_submission_suggestion_title_only(db: Session) -> None:
    """Test creating a submission suggestion with only a title change."""
    moderator = _create_test_user(db)
    submission_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    submission = _create_test_submission(db, author_id=submission_author.id, site=site)

    suggestion_in = SubmissionSuggestionCreate(
        submission_uuid=submission.uuid,
        title="New Title Only",
        desc=None,
        comment=None,
    )

    suggestion = crud.submission_suggestion.create_with_author(
        db, obj_in=suggestion_in, author_id=suggester.id, submission=submission
    )

    assert suggestion is not None
    assert suggestion.title == "New Title Only"


def test_create_submission_suggestion_with_desc(db: Session) -> None:
    """Test creating a submission suggestion with title and description."""
    moderator = _create_test_user(db)
    submission_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    submission = _create_test_submission(db, author_id=submission_author.id, site=site)

    suggestion_in = SubmissionSuggestionCreate(
        submission_uuid=submission.uuid,
        title="Updated Title",
        desc=RichText(
            source="New description",
            rendered_text="New description",
            editor="tiptap",
        ),
    )

    suggestion = crud.submission_suggestion.create_with_author(
        db, obj_in=suggestion_in, author_id=suggester.id, submission=submission
    )

    assert suggestion is not None
    assert suggestion.title == "Updated Title"


def test_get_submission_suggestion_by_id(db: Session) -> None:
    """Test getting a submission suggestion by ID."""
    moderator = _create_test_user(db)
    submission_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    submission = _create_test_submission(db, author_id=submission_author.id, site=site)

    suggestion_in = SubmissionSuggestionCreate(
        submission_uuid=submission.uuid,
        title="Test Title",
    )

    suggestion = crud.submission_suggestion.create_with_author(
        db, obj_in=suggestion_in, author_id=suggester.id, submission=submission
    )

    retrieved = crud.submission_suggestion.get(db, id=suggestion.id)
    assert retrieved is not None
    assert retrieved.id == suggestion.id


def test_get_submission_suggestion_by_uuid(db: Session) -> None:
    """Test getting a submission suggestion by UUID."""
    moderator = _create_test_user(db)
    submission_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    submission = _create_test_submission(db, author_id=submission_author.id, site=site)

    suggestion_in = SubmissionSuggestionCreate(
        submission_uuid=submission.uuid,
        title="Test Title",
    )

    suggestion = crud.submission_suggestion.create_with_author(
        db, obj_in=suggestion_in, author_id=suggester.id, submission=submission
    )

    retrieved = crud.submission_suggestion.get_by_uuid(db, uuid=suggestion.uuid)
    assert retrieved is not None
    assert retrieved.uuid == suggestion.uuid


def test_get_submission_suggestion_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent submission suggestion."""
    result = crud.submission_suggestion.get(db, id=99999999)
    assert result is None


def test_update_submission_suggestion_status_to_accepted(db: Session) -> None:
    """Test updating submission suggestion status to accepted."""
    moderator = _create_test_user(db)
    submission_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    submission = _create_test_submission(db, author_id=submission_author.id, site=site)

    suggestion_in = SubmissionSuggestionCreate(
        submission_uuid=submission.uuid,
        title="Test Title",
    )

    suggestion = crud.submission_suggestion.create_with_author(
        db, obj_in=suggestion_in, author_id=suggester.id, submission=submission
    )

    assert suggestion.status == "pending"

    updated = crud.submission_suggestion.update(
        db, db_obj=suggestion, obj_in=SubmissionSuggestionUpdate(status="accepted")
    )

    assert updated.status == "accepted"


def test_update_submission_suggestion_status_to_rejected(db: Session) -> None:
    """Test updating submission suggestion status to rejected."""
    moderator = _create_test_user(db)
    submission_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    submission = _create_test_submission(db, author_id=submission_author.id, site=site)

    suggestion_in = SubmissionSuggestionCreate(
        submission_uuid=submission.uuid,
        title="Test Title",
    )

    suggestion = crud.submission_suggestion.create_with_author(
        db, obj_in=suggestion_in, author_id=suggester.id, submission=submission
    )

    updated = crud.submission_suggestion.update(
        db, db_obj=suggestion, obj_in=SubmissionSuggestionUpdate(status="rejected")
    )

    assert updated.status == "rejected"


def test_update_submission_suggestion_status_to_retracted(db: Session) -> None:
    """Test updating submission suggestion status to retracted."""
    moderator = _create_test_user(db)
    submission_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    submission = _create_test_submission(db, author_id=submission_author.id, site=site)

    suggestion_in = SubmissionSuggestionCreate(
        submission_uuid=submission.uuid,
        title="Test Title",
    )

    suggestion = crud.submission_suggestion.create_with_author(
        db, obj_in=suggestion_in, author_id=suggester.id, submission=submission
    )

    updated = crud.submission_suggestion.update(
        db, db_obj=suggestion, obj_in=SubmissionSuggestionUpdate(status="retracted")
    )

    assert updated.status == "retracted"


def test_submission_suggestion_timestamps(db: Session) -> None:
    """Test that submission suggestions have correct timestamps."""
    moderator = _create_test_user(db)
    submission_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    submission = _create_test_submission(db, author_id=submission_author.id, site=site)

    before_create = datetime.datetime.now(tz=datetime.timezone.utc)

    suggestion_in = SubmissionSuggestionCreate(
        submission_uuid=submission.uuid,
        title="Test Title",
    )

    suggestion = crud.submission_suggestion.create_with_author(
        db, obj_in=suggestion_in, author_id=suggester.id, submission=submission
    )

    after_create = datetime.datetime.now(tz=datetime.timezone.utc)

    assert suggestion.created_at is not None
    assert before_create <= suggestion.created_at <= after_create


def test_multiple_suggestions_for_same_submission(db: Session) -> None:
    """Test that multiple users can suggest edits for the same submission."""
    moderator = _create_test_user(db)
    submission_author = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    submission = _create_test_submission(db, author_id=submission_author.id, site=site)

    suggestions = []
    for i in range(3):
        suggester = _create_test_user(db)
        suggestion_in = SubmissionSuggestionCreate(
            submission_uuid=submission.uuid,
            title=f"Title Suggestion {i}",
            comment=f"Suggestion {i}",
        )
        suggestion = crud.submission_suggestion.create_with_author(
            db, obj_in=suggestion_in, author_id=suggester.id, submission=submission
        )
        suggestions.append(suggestion)

    assert len(suggestions) == 3
    assert all(s.submission_id == submission.id for s in suggestions)


def test_same_user_multiple_suggestions(db: Session) -> None:
    """Test that the same user can make multiple suggestions for a submission."""
    moderator = _create_test_user(db)
    submission_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    submission = _create_test_submission(db, author_id=submission_author.id, site=site)

    suggestions = []
    for i in range(2):
        suggestion_in = SubmissionSuggestionCreate(
            submission_uuid=submission.uuid,
            title=f"Revision {i}",
        )
        suggestion = crud.submission_suggestion.create_with_author(
            db, obj_in=suggestion_in, author_id=suggester.id, submission=submission
        )
        suggestions.append(suggestion)

    assert len(suggestions) == 2
    assert all(s.author_id == suggester.id for s in suggestions)


def test_suggestions_for_different_submissions(db: Session) -> None:
    """Test that a user can suggest edits for different submissions."""
    moderator = _create_test_user(db)
    submission_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    submission1 = _create_test_submission(db, author_id=submission_author.id, site=site)
    submission2 = _create_test_submission(db, author_id=submission_author.id, site=site)

    for submission in [submission1, submission2]:
        suggestion_in = SubmissionSuggestionCreate(
            submission_uuid=submission.uuid,
            title="Suggested Title",
        )
        suggestion = crud.submission_suggestion.create_with_author(
            db, obj_in=suggestion_in, author_id=suggester.id, submission=submission
        )
        assert suggestion is not None
        assert suggestion.submission_id == submission.id
