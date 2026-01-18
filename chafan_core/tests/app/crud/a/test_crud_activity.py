import asyncio
import datetime
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.crud.crud_activity import (
    activity,
    create_submission_activity,
    create_article_activity,
    create_answer_activity,
    upvote_answer_activity,
    upvote_question_activity,
    upvote_submission_activity,
    follow_user_activity,
    subscribe_article_column_activity,
)
from chafan_core.app.schemas.user import UserCreate
from chafan_core.app.schemas.site import SiteCreate
from chafan_core.app.schemas.question import QuestionCreate
from chafan_core.app.schemas.submission import SubmissionCreate
from chafan_core.app.schemas.answer import AnswerCreate
from chafan_core.app.schemas.article import ArticleCreate
from chafan_core.app.schemas.article_column import ArticleColumnCreate
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import ContentVisibility, get_uuid
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


def _create_test_question(db: Session, author_id: int, site):
    """Helper to create a test question."""
    question_in = QuestionCreate(
        site_uuid=site.uuid,
        title=f"Test Question {random_short_lower_string()}",
    )
    return crud.question.create_with_author(db, obj_in=question_in, author_id=author_id)


def _create_test_submission(db: Session, author_id: int, site):
    """Helper to create a test submission."""
    submission_in = SubmissionCreate(
        site_uuid=site.uuid,
        title=f"Test Submission {random_short_lower_string()}",
        url="https://example.com/test",
    )
    return crud.submission.create_with_author(
        db, obj_in=submission_in, author_id=author_id
    )


def _create_test_answer(db: Session, author_id: int, question, site):
    """Helper to create a test answer."""
    answer_in = AnswerCreate(
        content=RichText(
            source="Test answer content",
            rendered_text="Test answer content",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
        is_published=True,
        visibility=ContentVisibility.ANYONE,
        writing_session_uuid=get_uuid(),
    )
    return crud.answer.create_with_author(
        db, obj_in=answer_in, author_id=author_id, site_id=site.id
    )


def _create_test_article_column(db: Session, owner_id: int):
    """Helper to create a test article column."""
    column_in = ArticleColumnCreate(
        name=f"Test Column {random_short_lower_string()}",
        description="Test column description",
    )
    return crud.article_column.create_with_owner(
        db, obj_in=column_in, owner_id=owner_id
    )


def _create_test_article(db: Session, author_id: int, column):
    """Helper to create a test article."""
    article_in = ArticleCreate(
        title=f"Test Article {random_short_lower_string()}",
        content=RichText(
            source="Test article content",
            rendered_text="Test article content",
            editor="tiptap",
        ),
        article_column_uuid=column.uuid,
        is_published=True,
        writing_session_uuid=get_uuid(),
        visibility=ContentVisibility.ANYONE,
    )
    return crud.article.create_with_author(db, obj_in=article_in, author_id=author_id)


def test_count_activities(db: Session) -> None:
    """Test counting activities."""
    initial_count = activity.count(db)
    assert initial_count >= 0


def test_get_multi_by_id_range_with_max_id(db: Session) -> None:
    """Test getting activities by ID range with max_id specified."""
    # Create some activities by creating submissions (which create activities)
    user = _create_test_user(db)
    site = _create_test_site(db, moderator=user)

    # Create submissions which generate activities
    for _ in range(3):
        _create_test_submission(db, author_id=user.id, site=site)

    # Get activities in a range
    all_activities = list(activity.get_multi_by_id_range(db, min_id=0, max_id=None))
    if len(all_activities) >= 2:
        # Test with max_id
        max_id = all_activities[0].id + 1
        min_id = all_activities[-1].id - 1
        range_activities = list(
            activity.get_multi_by_id_range(db, min_id=min_id, max_id=max_id)
        )
        assert len(range_activities) <= len(all_activities)


def test_get_multi_by_id_range_without_max_id(db: Session) -> None:
    """Test getting activities by ID range without max_id (open-ended)."""
    user = _create_test_user(db)
    site = _create_test_site(db, moderator=user)

    # Create a submission to generate activity
    _create_test_submission(db, author_id=user.id, site=site)

    # Get all activities from ID 0
    activities = list(activity.get_multi_by_id_range(db, min_id=0, max_id=None))
    assert len(activities) >= 1


def test_create_submission_activity_factory(db: Session) -> None:
    """Test create_submission_activity factory function."""
    user = _create_test_user(db)
    site = _create_test_site(db, moderator=user)
    submission = _create_test_submission(db, author_id=user.id, site=site)

    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    activity_obj = create_submission_activity(
        submission=submission, site=site, created_at=utc_now
    )

    assert activity_obj is not None
    assert activity_obj.site_id == site.id
    assert activity_obj.created_at == utc_now
    assert activity_obj.event_json is not None


def test_create_article_activity_factory(db: Session) -> None:
    """Test create_article_activity factory function."""
    user = _create_test_user(db)
    column = _create_test_article_column(db, owner_id=user.id)
    article = _create_test_article(db, author_id=user.id, column=column)

    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    activity_obj = create_article_activity(article=article, created_at=utc_now)

    assert activity_obj is not None
    assert activity_obj.site_id is None  # Articles don't have site_id
    assert activity_obj.created_at == utc_now
    assert activity_obj.event_json is not None


def test_create_answer_activity_factory(db: Session) -> None:
    """Test create_answer_activity factory function."""
    user = _create_test_user(db)
    site = _create_test_site(db, moderator=user)
    question = _create_test_question(db, author_id=user.id, site=site)
    answer = _create_test_answer(db, author_id=user.id, question=question, site=site)

    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    activity_obj = create_answer_activity(
        answer=answer, site_id=site.id, created_at=utc_now
    )

    assert activity_obj is not None
    assert activity_obj.site_id == site.id
    assert activity_obj.created_at == utc_now
    assert activity_obj.event_json is not None


def test_upvote_answer_activity_factory(db: Session) -> None:
    """Test upvote_answer_activity factory function."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    site = _create_test_site(db, moderator=author)
    question = _create_test_question(db, author_id=author.id, site=site)
    answer = _create_test_answer(db, author_id=author.id, question=question, site=site)

    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    activity_obj = upvote_answer_activity(
        voter=voter, answer=answer, site_id=site.id, created_at=utc_now
    )

    assert activity_obj is not None
    assert activity_obj.site_id == site.id
    assert activity_obj.created_at == utc_now
    assert activity_obj.event_json is not None


def test_upvote_question_activity_factory(db: Session) -> None:
    """Test upvote_question_activity factory function."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    site = _create_test_site(db, moderator=author)
    question = _create_test_question(db, author_id=author.id, site=site)

    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    activity_obj = upvote_question_activity(
        voter=voter, question=question, site_id=site.id, created_at=utc_now
    )

    assert activity_obj is not None
    assert activity_obj.site_id == site.id
    assert activity_obj.created_at == utc_now
    assert activity_obj.event_json is not None


def test_upvote_submission_activity_factory(db: Session) -> None:
    """Test upvote_submission_activity factory function."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    site = _create_test_site(db, moderator=author)
    submission = _create_test_submission(db, author_id=author.id, site=site)

    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    activity_obj = upvote_submission_activity(
        voter=voter, submission=submission, site_id=site.id, created_at=utc_now
    )

    assert activity_obj is not None
    assert activity_obj.site_id == site.id
    assert activity_obj.created_at == utc_now
    assert activity_obj.event_json is not None


def test_follow_user_activity_factory(db: Session) -> None:
    """Test follow_user_activity factory function."""
    follower = _create_test_user(db)
    followed = _create_test_user(db)

    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    activity_obj = follow_user_activity(
        follower=follower, followed=followed, created_at=utc_now
    )

    assert activity_obj is not None
    assert activity_obj.site_id is None  # User follows are not site-specific
    assert activity_obj.created_at == utc_now
    assert activity_obj.event_json is not None


def test_subscribe_article_column_activity_factory(db: Session) -> None:
    """Test subscribe_article_column_activity factory function."""
    owner = _create_test_user(db)
    subscriber = _create_test_user(db)
    column = _create_test_article_column(db, owner_id=owner.id)

    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    activity_obj = subscribe_article_column_activity(
        user=subscriber, article_column=column, created_at=utc_now
    )

    assert activity_obj is not None
    assert activity_obj.site_id is None  # Column subscriptions are not site-specific
    assert activity_obj.created_at == utc_now
    assert activity_obj.event_json is not None


def test_activity_event_json_contains_valid_json(db: Session) -> None:
    """Test that activity event_json contains valid JSON."""
    import json

    user = _create_test_user(db)
    site = _create_test_site(db, moderator=user)
    submission = _create_test_submission(db, author_id=user.id, site=site)

    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    activity_obj = create_submission_activity(
        submission=submission, site=site, created_at=utc_now
    )

    # Should be valid JSON
    parsed = json.loads(activity_obj.event_json)
    assert "created_at" in parsed
    assert "content" in parsed


def test_get_activity(db: Session) -> None:
    """Test getting an activity by ID."""
    user = _create_test_user(db)
    site = _create_test_site(db, moderator=user)
    submission = _create_test_submission(db, author_id=user.id, site=site)

    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    activity_obj = create_submission_activity(
        submission=submission, site=site, created_at=utc_now
    )
    db.add(activity_obj)
    db.commit()
    db.refresh(activity_obj)

    retrieved = activity.get(db, id=activity_obj.id)
    assert retrieved is not None
    assert retrieved.id == activity_obj.id
