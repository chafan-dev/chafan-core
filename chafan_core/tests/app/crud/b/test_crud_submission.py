import asyncio
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.submission import SubmissionCreate, SubmissionUpdate
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


def _create_test_site(db: Session, moderator):
    """Helper to create a test site."""
    from chafan_core.app.schemas.site import SiteCreate

    site_in = SiteCreate(
        name=f"Test Site {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
        description="Test site",
        permission_type="private",
    )
    return crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=None
    )


def test_create_submission_with_author(db: Session) -> None:
    """Test creating a submission with an author."""
    user = _create_test_user(db)
    site = _create_test_site(db, moderator=user)

    submission_in = SubmissionCreate(
        site_uuid=site.uuid,
        title=f"Test Submission {random_short_lower_string()}",
        url="https://example.com/test",
    )

    submission = crud.submission.create_with_author(
        db, obj_in=submission_in, author_id=user.id
    )

    assert submission is not None
    assert submission.author_id == user.id
    assert submission.site_id == site.id
    assert submission.title == submission_in.title
    assert submission.url == str(submission_in.url)
    assert submission.uuid is not None
    assert submission.created_at is not None
    assert submission.updated_at is not None


def test_create_submission_without_url(db: Session) -> None:
    """Test creating a submission without a URL."""
    user = _create_test_user(db)
    site = _create_test_site(db, moderator=user)

    submission_in = SubmissionCreate(
        site_uuid=site.uuid,
        title=f"Test Submission No URL {random_short_lower_string()}",
    )

    submission = crud.submission.create_with_author(
        db, obj_in=submission_in, author_id=user.id
    )

    assert submission is not None
    assert submission.url is None


def test_get_submission_by_uuid(db: Session) -> None:
    """Test retrieving a submission by UUID."""
    user = _create_test_user(db)
    site = _create_test_site(db, moderator=user)

    submission_in = SubmissionCreate(
        site_uuid=site.uuid,
        title=f"Test Submission for UUID lookup {random_short_lower_string()}",
        url="https://example.com/uuid-test",
    )

    submission = crud.submission.create_with_author(
        db, obj_in=submission_in, author_id=user.id
    )

    retrieved_submission = crud.submission.get_by_uuid(db, uuid=submission.uuid)
    assert retrieved_submission is not None
    assert retrieved_submission.id == submission.id
    assert retrieved_submission.uuid == submission.uuid


def test_submission_upvote(db: Session) -> None:
    """Test upvoting a submission."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    site = _create_test_site(db, moderator=author)

    submission_in = SubmissionCreate(
        site_uuid=site.uuid,
        title=f"Test Submission for upvote {random_short_lower_string()}",
        url="https://example.com/upvote-test",
    )

    submission = crud.submission.create_with_author(
        db, obj_in=submission_in, author_id=author.id
    )

    initial_upvotes = submission.upvotes_count

    # Upvote the submission
    updated_submission = crud.submission.upvote(db, db_obj=submission, voter=voter)
    assert updated_submission.upvotes_count == initial_upvotes + 1

    # Upvoting again should not increase count (idempotent)
    updated_submission = crud.submission.upvote(db, db_obj=submission, voter=voter)
    assert updated_submission.upvotes_count == initial_upvotes + 1


def test_submission_cancel_upvote(db: Session) -> None:
    """Test canceling an upvote on a submission."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    site = _create_test_site(db, moderator=author)

    submission_in = SubmissionCreate(
        site_uuid=site.uuid,
        title=f"Test Submission for cancel upvote {random_short_lower_string()}",
        url="https://example.com/cancel-upvote-test",
    )

    submission = crud.submission.create_with_author(
        db, obj_in=submission_in, author_id=author.id
    )

    # First upvote
    submission = crud.submission.upvote(db, db_obj=submission, voter=voter)
    upvotes_after_upvote = submission.upvotes_count

    # Cancel upvote
    submission = crud.submission.cancel_upvote(db, db_obj=submission, voter=voter)
    assert submission.upvotes_count == upvotes_after_upvote - 1

    # Canceling again should not decrease count
    submission = crud.submission.cancel_upvote(db, db_obj=submission, voter=voter)
    assert submission.upvotes_count == upvotes_after_upvote - 1


def test_submission_reupvote_after_cancel(db: Session) -> None:
    """Test re-upvoting a submission after canceling."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    site = _create_test_site(db, moderator=author)

    submission_in = SubmissionCreate(
        site_uuid=site.uuid,
        title=f"Test Submission for reupvote {random_short_lower_string()}",
        url="https://example.com/reupvote-test",
    )

    submission = crud.submission.create_with_author(
        db, obj_in=submission_in, author_id=author.id
    )

    # Upvote
    submission = crud.submission.upvote(db, db_obj=submission, voter=voter)
    upvotes_after_first_upvote = submission.upvotes_count

    # Cancel
    submission = crud.submission.cancel_upvote(db, db_obj=submission, voter=voter)
    assert submission.upvotes_count == upvotes_after_first_upvote - 1

    # Re-upvote (reactivate cancelled upvote)
    submission = crud.submission.upvote(db, db_obj=submission, voter=voter)
    assert submission.upvotes_count == upvotes_after_first_upvote


def test_update_submission_topics(db: Session) -> None:
    """Test updating submission topics."""
    user = _create_test_user(db)
    site = _create_test_site(db, moderator=user)

    submission_in = SubmissionCreate(
        site_uuid=site.uuid,
        title=f"Test Submission for topics {random_short_lower_string()}",
        url="https://example.com/topics-test",
    )

    submission = crud.submission.create_with_author(
        db, obj_in=submission_in, author_id=user.id
    )

    # Create test topics
    from chafan_core.app.schemas.topic import TopicCreate

    topic1_in = TopicCreate(name=f"SubmissionTopic1 {random_short_lower_string()}")
    topic2_in = TopicCreate(name=f"SubmissionTopic2 {random_short_lower_string()}")

    topic1 = crud.topic.create(db, obj_in=topic1_in)
    topic2 = crud.topic.create(db, obj_in=topic2_in)

    # Update topics
    submission = crud.submission.update_topics(
        db, db_obj=submission, new_topics=[topic1, topic2]
    )

    assert len(submission.topics) == 2
    topic_ids = [t.id for t in submission.topics]
    assert topic1.id in topic_ids
    assert topic2.id in topic_ids


def test_update_submission_topics_clear(db: Session) -> None:
    """Test clearing submission topics."""
    user = _create_test_user(db)
    site = _create_test_site(db, moderator=user)

    submission_in = SubmissionCreate(
        site_uuid=site.uuid,
        title=f"Test Submission for clearing topics {random_short_lower_string()}",
        url="https://example.com/clear-topics-test",
    )

    submission = crud.submission.create_with_author(
        db, obj_in=submission_in, author_id=user.id
    )

    # Create and add a topic
    from chafan_core.app.schemas.topic import TopicCreate

    topic_in = TopicCreate(name=f"SubmissionTopic {random_short_lower_string()}")
    topic = crud.topic.create(db, obj_in=topic_in)

    submission = crud.submission.update_topics(
        db, db_obj=submission, new_topics=[topic]
    )
    assert len(submission.topics) == 1

    # Clear topics
    submission = crud.submission.update_topics(db, db_obj=submission, new_topics=[])
    assert len(submission.topics) == 0


def test_get_all_valid(db: Session) -> None:
    """Test getting all valid (not hidden) submissions."""
    user = _create_test_user(db)
    site = _create_test_site(db, moderator=user)

    # Create a normal submission
    normal_submission_in = SubmissionCreate(
        site_uuid=site.uuid,
        title=f"Test Submission normal {random_short_lower_string()}",
        url="https://example.com/normal-test",
    )

    normal_submission = crud.submission.create_with_author(
        db, obj_in=normal_submission_in, author_id=user.id
    )

    # Create a hidden submission
    hidden_submission_in = SubmissionCreate(
        site_uuid=site.uuid,
        title=f"Test Submission hidden {random_short_lower_string()}",
        url="https://example.com/hidden-test",
    )

    hidden_submission = crud.submission.create_with_author(
        db, obj_in=hidden_submission_in, author_id=user.id
    )
    crud.submission.update(db, db_obj=hidden_submission, obj_in={"is_hidden": True})

    all_valid = crud.submission.get_all_valid(db)
    valid_ids = [s.id for s in all_valid]

    assert normal_submission.id in valid_ids
    assert hidden_submission.id not in valid_ids


def test_count_upvotes(db: Session) -> None:
    """Test counting upvotes on a submission."""
    author = _create_test_user(db)
    voter1 = _create_test_user(db)
    voter2 = _create_test_user(db)
    site = _create_test_site(db, moderator=author)

    submission_in = SubmissionCreate(
        site_uuid=site.uuid,
        title=f"Test Submission for count upvotes {random_short_lower_string()}",
        url="https://example.com/count-upvotes-test",
    )

    submission = crud.submission.create_with_author(
        db, obj_in=submission_in, author_id=author.id
    )

    # Initially no upvotes
    assert crud.submission.count_upvotes(db, submission) == 0

    # Add upvotes
    crud.submission.upvote(db, db_obj=submission, voter=voter1)
    assert crud.submission.count_upvotes(db, submission) == 1

    crud.submission.upvote(db, db_obj=submission, voter=voter2)
    assert crud.submission.count_upvotes(db, submission) == 2


def test_count_upvotes_excludes_cancelled(db: Session) -> None:
    """Test that count_upvotes excludes cancelled upvotes."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    site = _create_test_site(db, moderator=author)

    submission_in = SubmissionCreate(
        site_uuid=site.uuid,
        title=f"Test Submission for cancelled upvotes {random_short_lower_string()}",
        url="https://example.com/cancelled-upvotes-test",
    )

    submission = crud.submission.create_with_author(
        db, obj_in=submission_in, author_id=author.id
    )

    # Upvote then cancel
    crud.submission.upvote(db, db_obj=submission, voter=voter)
    assert crud.submission.count_upvotes(db, submission) == 1

    crud.submission.cancel_upvote(db, db_obj=submission, voter=voter)
    assert crud.submission.count_upvotes(db, submission) == 0


def test_update_submission(db: Session) -> None:
    """Test updating a submission."""
    user = _create_test_user(db)
    site = _create_test_site(db, moderator=user)

    submission_in = SubmissionCreate(
        site_uuid=site.uuid,
        title=f"Original Title {random_short_lower_string()}",
        url="https://example.com/original",
    )

    submission = crud.submission.create_with_author(
        db, obj_in=submission_in, author_id=user.id
    )

    new_title = f"Updated Title {random_short_lower_string()}"
    crud.submission.update(db, db_obj=submission, obj_in={"title": new_title})

    db.refresh(submission)
    assert submission.title == new_title


def test_get_submission_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent submission."""
    result = crud.submission.get(db, id=99999999)
    assert result is None


def test_get_submission_by_uuid_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get_by_uuid returns None for non-existent submission."""
    result = crud.submission.get_by_uuid(db, uuid="nonexistent-submission-uuid")
    assert result is None
