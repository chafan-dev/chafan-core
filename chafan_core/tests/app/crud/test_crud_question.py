import asyncio
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.question import QuestionCreate, QuestionUpdate
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


def _create_test_site(db: Session):
    """Helper to create a test site."""
    from chafan_core.app.schemas.site import SiteCreate

    site_in = SiteCreate(
        name=f"Test Site {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
    )
    return crud.site.create(db, obj_in=site_in)


def test_create_question_with_author(db: Session) -> None:
    """Test creating a question with an author."""
    user = _create_test_user(db)
    site = _create_test_site(db)

    question_in = QuestionCreate(
        site_uuid=site.uuid,
        title=f"Test Question {random_short_lower_string()}",
    )

    question = crud.question.create_with_author(
        db, obj_in=question_in, author_id=user.id
    )

    assert question is not None
    assert question.author_id == user.id
    assert question.editor_id == user.id
    assert question.site_id == site.id
    assert question.title == question_in.title
    assert question.uuid is not None
    assert question.created_at is not None
    assert question.updated_at is not None


def test_get_question_by_uuid(db: Session) -> None:
    """Test retrieving a question by UUID."""
    user = _create_test_user(db)
    site = _create_test_site(db)

    question_in = QuestionCreate(
        site_uuid=site.uuid,
        title=f"Test Question for UUID lookup {random_short_lower_string()}",
    )

    question = crud.question.create_with_author(
        db, obj_in=question_in, author_id=user.id
    )

    retrieved_question = crud.question.get_by_uuid(db, uuid=question.uuid)
    assert retrieved_question is not None
    assert retrieved_question.id == question.id
    assert retrieved_question.uuid == question.uuid


def test_get_question_by_id(db: Session) -> None:
    """Test retrieving a question by ID."""
    user = _create_test_user(db)
    site = _create_test_site(db)

    question_in = QuestionCreate(
        site_uuid=site.uuid,
        title=f"Test Question for ID lookup {random_short_lower_string()}",
    )

    question = crud.question.create_with_author(
        db, obj_in=question_in, author_id=user.id
    )

    retrieved_question = crud.question.get_by_id(db, id=question.id)
    assert retrieved_question is not None
    assert retrieved_question.id == question.id


def test_question_upvote(db: Session) -> None:
    """Test upvoting a question."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    site = _create_test_site(db)

    question_in = QuestionCreate(
        site_uuid=site.uuid,
        title=f"Test Question for upvote {random_short_lower_string()}",
    )

    question = crud.question.create_with_author(
        db, obj_in=question_in, author_id=author.id
    )

    initial_upvotes = question.upvotes_count

    # Upvote the question
    updated_question = crud.question.upvote(db, db_obj=question, voter=voter)
    assert updated_question.upvotes_count == initial_upvotes + 1

    # Upvoting again should not increase count (idempotent)
    updated_question = crud.question.upvote(db, db_obj=question, voter=voter)
    assert updated_question.upvotes_count == initial_upvotes + 1


def test_question_cancel_upvote(db: Session) -> None:
    """Test canceling an upvote on a question."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    site = _create_test_site(db)

    question_in = QuestionCreate(
        site_uuid=site.uuid,
        title=f"Test Question for cancel upvote {random_short_lower_string()}",
    )

    question = crud.question.create_with_author(
        db, obj_in=question_in, author_id=author.id
    )

    # First upvote
    question = crud.question.upvote(db, db_obj=question, voter=voter)
    upvotes_after_upvote = question.upvotes_count

    # Cancel upvote
    question = crud.question.cancel_upvote(db, db_obj=question, voter=voter)
    assert question.upvotes_count == upvotes_after_upvote - 1

    # Canceling again should not decrease count
    question = crud.question.cancel_upvote(db, db_obj=question, voter=voter)
    assert question.upvotes_count == upvotes_after_upvote - 1


def test_question_reupvote_after_cancel(db: Session) -> None:
    """Test re-upvoting a question after canceling."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    site = _create_test_site(db)

    question_in = QuestionCreate(
        site_uuid=site.uuid,
        title=f"Test Question for reupvote {random_short_lower_string()}",
    )

    question = crud.question.create_with_author(
        db, obj_in=question_in, author_id=author.id
    )

    # Upvote
    question = crud.question.upvote(db, db_obj=question, voter=voter)
    upvotes_after_first_upvote = question.upvotes_count

    # Cancel
    question = crud.question.cancel_upvote(db, db_obj=question, voter=voter)
    assert question.upvotes_count == upvotes_after_first_upvote - 1

    # Re-upvote (reactivate cancelled upvote)
    question = crud.question.upvote(db, db_obj=question, voter=voter)
    assert question.upvotes_count == upvotes_after_first_upvote


def test_update_question_topics(db: Session) -> None:
    """Test updating question topics."""
    user = _create_test_user(db)
    site = _create_test_site(db)

    question_in = QuestionCreate(
        site_uuid=site.uuid,
        title=f"Test Question for topics {random_short_lower_string()}",
    )

    question = crud.question.create_with_author(
        db, obj_in=question_in, author_id=user.id
    )

    # Create test topics
    from chafan_core.app.schemas.topic import TopicCreate

    topic1_in = TopicCreate(name=f"Topic1 {random_short_lower_string()}")
    topic2_in = TopicCreate(name=f"Topic2 {random_short_lower_string()}")

    topic1 = crud.topic.create(db, obj_in=topic1_in)
    topic2 = crud.topic.create(db, obj_in=topic2_in)

    # Update topics
    question = crud.question.update_topics(
        db, db_obj=question, new_topics=[topic1, topic2]
    )

    assert len(question.topics) == 2
    topic_ids = [t.id for t in question.topics]
    assert topic1.id in topic_ids
    assert topic2.id in topic_ids


def test_update_question_topics_clear(db: Session) -> None:
    """Test clearing question topics."""
    user = _create_test_user(db)
    site = _create_test_site(db)

    question_in = QuestionCreate(
        site_uuid=site.uuid,
        title=f"Test Question for clearing topics {random_short_lower_string()}",
    )

    question = crud.question.create_with_author(
        db, obj_in=question_in, author_id=user.id
    )

    # Create and add topics
    from chafan_core.app.schemas.topic import TopicCreate

    topic_in = TopicCreate(name=f"Topic {random_short_lower_string()}")
    topic = crud.topic.create(db, obj_in=topic_in)

    question = crud.question.update_topics(db, db_obj=question, new_topics=[topic])
    assert len(question.topics) == 1

    # Clear topics
    question = crud.question.update_topics(db, db_obj=question, new_topics=[])
    assert len(question.topics) == 0


def test_get_placed_at_home(db: Session) -> None:
    """Test getting questions placed at home."""
    user = _create_test_user(db)
    site = _create_test_site(db)

    # Create a question and place it at home
    question_in = QuestionCreate(
        site_uuid=site.uuid,
        title=f"Test Question for home {random_short_lower_string()}",
    )

    question = crud.question.create_with_author(
        db, obj_in=question_in, author_id=user.id
    )

    # Set is_placed_at_home to True
    crud.question.update(db, db_obj=question, obj_in={"is_placed_at_home": True})

    placed_at_home = crud.question.get_placed_at_home(db)
    placed_ids = [q.id for q in placed_at_home]

    assert question.id in placed_ids


def test_get_all_valid(db: Session) -> None:
    """Test getting all valid (not hidden) questions."""
    user = _create_test_user(db)
    site = _create_test_site(db)

    # Create a normal question
    question_in = QuestionCreate(
        site_uuid=site.uuid,
        title=f"Test Question normal {random_short_lower_string()}",
    )

    normal_question = crud.question.create_with_author(
        db, obj_in=question_in, author_id=user.id
    )

    # Create a hidden question
    hidden_question_in = QuestionCreate(
        site_uuid=site.uuid,
        title=f"Test Question hidden {random_short_lower_string()}",
    )

    hidden_question = crud.question.create_with_author(
        db, obj_in=hidden_question_in, author_id=user.id
    )
    crud.question.update(db, db_obj=hidden_question, obj_in={"is_hidden": True})

    all_valid = crud.question.get_all_valid(db)
    valid_ids = [q.id for q in all_valid]

    assert normal_question.id in valid_ids
    assert hidden_question.id not in valid_ids


def test_update_question(db: Session) -> None:
    """Test updating a question."""
    user = _create_test_user(db)
    site = _create_test_site(db)

    question_in = QuestionCreate(
        site_uuid=site.uuid,
        title=f"Original Title {random_short_lower_string()}",
    )

    question = crud.question.create_with_author(
        db, obj_in=question_in, author_id=user.id
    )

    new_title = f"Updated Title {random_short_lower_string()}"
    crud.question.update(db, db_obj=question, obj_in={"title": new_title})

    db.refresh(question)
    assert question.title == new_title


def test_get_question_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent question."""
    result = crud.question.get(db, id=99999999)
    assert result is None


def test_get_question_by_uuid_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get_by_uuid returns None for non-existent question."""
    result = crud.question.get_by_uuid(db, uuid="nonexistent-uuid")
    assert result is None
