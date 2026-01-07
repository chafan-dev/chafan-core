import asyncio
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.answer import AnswerCreate, AnswerUpdate
from chafan_core.app.schemas.question import QuestionCreate
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.schemas.user import UserCreate
from chafan_core.utils.base import ContentVisibility, get_uuid
from chafan_core.tests.utils.utils import (
    random_email,
    random_password,
    random_short_lower_string,
    random_lower_string,
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


def _create_test_question(db: Session, author_id: int, site_id: int):
    """Helper to create a test question."""
    question_in = QuestionCreate(
        site_uuid=crud.site.get(db, id=site_id).uuid,
        title=f"Test Question {random_short_lower_string()}",
    )
    return crud.question.create_with_author(db, obj_in=question_in, author_id=author_id)


def test_create_answer_with_author(db: Session) -> None:
    """Test creating an answer with an author."""
    user = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=user.id, site_id=site.id)

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

    answer = crud.answer.create_with_author(
        db, obj_in=answer_in, author_id=user.id, site_id=site.id
    )

    assert answer is not None
    assert answer.author_id == user.id
    assert answer.question_id == question.id
    assert answer.site_id == site.id
    assert answer.is_published is True
    assert answer.body == "Test answer content"


def test_get_answer_by_uuid(db: Session) -> None:
    """Test retrieving an answer by UUID."""
    user = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=user.id, site_id=site.id)

    answer_in = AnswerCreate(
        content=RichText(
            source="Test answer for UUID lookup",
            rendered_text="Test answer for UUID lookup",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
        is_published=True,
        visibility=ContentVisibility.ANYONE,
        writing_session_uuid=get_uuid(),
    )

    answer = crud.answer.create_with_author(
        db, obj_in=answer_in, author_id=user.id, site_id=site.id
    )

    retrieved_answer = crud.answer.get_by_uuid(db, uuid=answer.uuid)
    assert retrieved_answer is not None
    assert retrieved_answer.id == answer.id
    assert retrieved_answer.uuid == answer.uuid


def test_answer_upvote(db: Session) -> None:
    """Test upvoting an answer."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=author.id, site_id=site.id)

    answer_in = AnswerCreate(
        content=RichText(
            source="Test answer for upvote",
            rendered_text="Test answer for upvote",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
        is_published=True,
        visibility=ContentVisibility.ANYONE,
        writing_session_uuid=get_uuid(),
    )

    answer = crud.answer.create_with_author(
        db, obj_in=answer_in, author_id=author.id, site_id=site.id
    )

    initial_upvotes = answer.upvotes_count

    # Upvote the answer
    updated_answer = crud.answer.upvote(db, db_obj=answer, voter=voter)
    assert updated_answer.upvotes_count == initial_upvotes + 1

    # Upvoting again should not increase count (idempotent)
    updated_answer = crud.answer.upvote(db, db_obj=answer, voter=voter)
    assert updated_answer.upvotes_count == initial_upvotes + 1


def test_answer_cancel_upvote(db: Session) -> None:
    """Test canceling an upvote on an answer."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=author.id, site_id=site.id)

    answer_in = AnswerCreate(
        content=RichText(
            source="Test answer for cancel upvote",
            rendered_text="Test answer for cancel upvote",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
        is_published=True,
        visibility=ContentVisibility.ANYONE,
        writing_session_uuid=get_uuid(),
    )

    answer = crud.answer.create_with_author(
        db, obj_in=answer_in, author_id=author.id, site_id=site.id
    )

    # First upvote
    answer = crud.answer.upvote(db, db_obj=answer, voter=voter)
    upvotes_after_upvote = answer.upvotes_count

    # Cancel upvote
    answer = crud.answer.cancel_upvote(db, db_obj=answer, voter=voter)
    assert answer.upvotes_count == upvotes_after_upvote - 1

    # Canceling again should not decrease count
    answer = crud.answer.cancel_upvote(db, db_obj=answer, voter=voter)
    assert answer.upvotes_count == upvotes_after_upvote - 1


def test_get_one_as_search_result_published(db: Session) -> None:
    """Test getting a published answer as search result."""
    user = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=user.id, site_id=site.id)

    answer_in = AnswerCreate(
        content=RichText(
            source="Published answer for search",
            rendered_text="Published answer for search",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
        is_published=True,
        visibility=ContentVisibility.ANYONE,
        writing_session_uuid=get_uuid(),
    )

    answer = crud.answer.create_with_author(
        db, obj_in=answer_in, author_id=user.id, site_id=site.id
    )

    result = crud.answer.get_one_as_search_result(db, id=answer.id)
    assert result is not None
    assert result.id == answer.id


def test_get_one_as_search_result_unpublished(db: Session) -> None:
    """Test that unpublished answers are not returned as search results."""
    user = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=user.id, site_id=site.id)

    answer_in = AnswerCreate(
        content=RichText(
            source="Unpublished answer for search",
            rendered_text="Unpublished answer for search",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
        is_published=False,  # Not published
        visibility=ContentVisibility.ANYONE,
        writing_session_uuid=get_uuid(),
    )

    answer = crud.answer.create_with_author(
        db, obj_in=answer_in, author_id=user.id, site_id=site.id
    )

    result = crud.answer.get_one_as_search_result(db, id=answer.id)
    assert result is None


def test_get_one_as_search_result_hidden_by_moderator(db: Session) -> None:
    """Test that answers hidden by moderator are not returned as search results."""
    user = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=user.id, site_id=site.id)

    answer_in = AnswerCreate(
        content=RichText(
            source="Hidden answer for search",
            rendered_text="Hidden answer for search",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
        is_published=True,
        visibility=ContentVisibility.ANYONE,
        writing_session_uuid=get_uuid(),
    )

    answer = crud.answer.create_with_author(
        db, obj_in=answer_in, author_id=user.id, site_id=site.id
    )

    # Hide by moderator
    crud.answer.update(db, db_obj=answer, obj_in={"is_hidden_by_moderator": True})

    result = crud.answer.get_one_as_search_result(db, id=answer.id)
    assert result is None


def test_get_all_published(db: Session) -> None:
    """Test getting all published answers."""
    user = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=user.id, site_id=site.id)

    # Create a published answer
    published_answer_in = AnswerCreate(
        content=RichText(
            source="Published answer",
            rendered_text="Published answer",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
        is_published=True,
        visibility=ContentVisibility.ANYONE,
        writing_session_uuid=get_uuid(),
    )

    published_answer = crud.answer.create_with_author(
        db, obj_in=published_answer_in, author_id=user.id, site_id=site.id
    )

    # Create an unpublished answer
    unpublished_answer_in = AnswerCreate(
        content=RichText(
            source="Unpublished answer",
            rendered_text="Unpublished answer",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
        is_published=False,
        visibility=ContentVisibility.ANYONE,
        writing_session_uuid=get_uuid(),
    )

    unpublished_answer = crud.answer.create_with_author(
        db, obj_in=unpublished_answer_in, author_id=user.id, site_id=site.id
    )

    all_published = crud.answer.get_all_published(db)
    published_ids = [a.id for a in all_published]

    assert published_answer.id in published_ids
    assert unpublished_answer.id not in published_ids


def test_delete_forever(db: Session) -> None:
    """Test permanently deleting an answer."""
    user = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=user.id, site_id=site.id)

    answer_in = AnswerCreate(
        content=RichText(
            source="Answer to be deleted",
            rendered_text="Answer to be deleted",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
        is_published=True,
        visibility=ContentVisibility.ANYONE,
        writing_session_uuid=get_uuid(),
    )

    answer = crud.answer.create_with_author(
        db, obj_in=answer_in, author_id=user.id, site_id=site.id
    )

    crud.answer.delete_forever(db, answer=answer)

    # Refresh to get updated state
    db.refresh(answer)

    assert answer.is_deleted is True
    assert answer.body == "[DELETED]"
    assert answer.body_prerendered_text == "[DELETED]"


def test_update_checked_cannot_unpublish(db: Session) -> None:
    """Test that update_checked prevents unpublishing a published answer."""
    user = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=user.id, site_id=site.id)

    answer_in = AnswerCreate(
        content=RichText(
            source="Published answer for update_checked",
            rendered_text="Published answer for update_checked",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
        is_published=True,
        visibility=ContentVisibility.ANYONE,
        writing_session_uuid=get_uuid(),
    )

    answer = crud.answer.create_with_author(
        db, obj_in=answer_in, author_id=user.id, site_id=site.id
    )

    # Should raise assertion error when trying to unpublish
    try:
        crud.answer.update_checked(db, db_obj=answer, obj_in={"is_published": False})
        assert False, "Expected assertion error"
    except AssertionError:
        pass  # Expected behavior


def test_get_all(db: Session) -> None:
    """Test getting all answers including deleted ones."""
    initial_count = len(crud.answer.get_all(db))

    user = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=user.id, site_id=site.id)

    answer_in = AnswerCreate(
        content=RichText(
            source="Answer for get_all test",
            rendered_text="Answer for get_all test",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
        is_published=True,
        visibility=ContentVisibility.ANYONE,
        writing_session_uuid=get_uuid(),
    )

    crud.answer.create_with_author(
        db, obj_in=answer_in, author_id=user.id, site_id=site.id
    )

    all_answers = crud.answer.get_all(db)
    assert len(all_answers) == initial_count + 1
