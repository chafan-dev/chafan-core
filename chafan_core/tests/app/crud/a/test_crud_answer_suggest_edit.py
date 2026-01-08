import asyncio
import datetime
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.answer_suggest_edit import (
    AnswerSuggestEditCreate,
    AnswerSuggestEditUpdate,
)
from chafan_core.app.schemas.answer import AnswerCreate
from chafan_core.app.schemas.question import QuestionCreate
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.schemas.user import UserCreate
from chafan_core.app.schemas.site import SiteCreate
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


def _create_test_answer(db: Session, author_id: int, question, site):
    """Helper to create a test answer."""
    answer_in = AnswerCreate(
        content=RichText(
            source="Original answer content",
            rendered_text="Original answer content",
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


def test_create_answer_suggest_edit_with_author(db: Session) -> None:
    """Test creating an answer suggest edit with an author."""
    moderator = _create_test_user(db)
    answer_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    question = _create_test_question(db, author_id=answer_author.id, site=site)
    answer = _create_test_answer(db, author_id=answer_author.id, question=question, site=site)

    suggest_edit_in = AnswerSuggestEditCreate(
        answer_uuid=answer.uuid,
        body_rich_text=RichText(
            source="Improved answer content",
            rendered_text="Improved answer content",
            editor="tiptap",
        ),
        comment="Fixed typos and improved clarity",
    )

    suggest_edit = crud.answer_suggest_edit.create_with_author(
        db, obj_in=suggest_edit_in, author_id=suggester.id, answer=answer
    )

    assert suggest_edit is not None
    assert suggest_edit.author_id == suggester.id
    assert suggest_edit.answer_id == answer.id
    assert suggest_edit.status == "pending"
    assert suggest_edit.comment == "Fixed typos and improved clarity"
    assert suggest_edit.uuid is not None
    assert suggest_edit.created_at is not None


def test_create_answer_suggest_edit_without_comment(db: Session) -> None:
    """Test creating an answer suggest edit without a comment."""
    moderator = _create_test_user(db)
    answer_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    question = _create_test_question(db, author_id=answer_author.id, site=site)
    answer = _create_test_answer(db, author_id=answer_author.id, question=question, site=site)

    suggest_edit_in = AnswerSuggestEditCreate(
        answer_uuid=answer.uuid,
        body_rich_text=RichText(
            source="Updated content",
            rendered_text="Updated content",
            editor="tiptap",
        ),
        comment=None,
    )

    suggest_edit = crud.answer_suggest_edit.create_with_author(
        db, obj_in=suggest_edit_in, author_id=suggester.id, answer=answer
    )

    assert suggest_edit is not None
    assert suggest_edit.comment is None


def test_get_answer_suggest_edit_by_id(db: Session) -> None:
    """Test getting an answer suggest edit by ID."""
    moderator = _create_test_user(db)
    answer_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    question = _create_test_question(db, author_id=answer_author.id, site=site)
    answer = _create_test_answer(db, author_id=answer_author.id, question=question, site=site)

    suggest_edit_in = AnswerSuggestEditCreate(
        answer_uuid=answer.uuid,
        body_rich_text=RichText(
            source="Content",
            rendered_text="Content",
            editor="tiptap",
        ),
    )

    suggest_edit = crud.answer_suggest_edit.create_with_author(
        db, obj_in=suggest_edit_in, author_id=suggester.id, answer=answer
    )

    retrieved = crud.answer_suggest_edit.get(db, id=suggest_edit.id)
    assert retrieved is not None
    assert retrieved.id == suggest_edit.id


def test_get_answer_suggest_edit_by_uuid(db: Session) -> None:
    """Test getting an answer suggest edit by UUID."""
    moderator = _create_test_user(db)
    answer_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    question = _create_test_question(db, author_id=answer_author.id, site=site)
    answer = _create_test_answer(db, author_id=answer_author.id, question=question, site=site)

    suggest_edit_in = AnswerSuggestEditCreate(
        answer_uuid=answer.uuid,
        body_rich_text=RichText(
            source="Content",
            rendered_text="Content",
            editor="tiptap",
        ),
    )

    suggest_edit = crud.answer_suggest_edit.create_with_author(
        db, obj_in=suggest_edit_in, author_id=suggester.id, answer=answer
    )

    retrieved = crud.answer_suggest_edit.get_by_uuid(db, uuid=suggest_edit.uuid)
    assert retrieved is not None
    assert retrieved.uuid == suggest_edit.uuid


def test_get_answer_suggest_edit_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent answer suggest edit."""
    result = crud.answer_suggest_edit.get(db, id=99999999)
    assert result is None


def test_update_answer_suggest_edit_status_to_accepted(db: Session) -> None:
    """Test updating answer suggest edit status to accepted."""
    moderator = _create_test_user(db)
    answer_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    question = _create_test_question(db, author_id=answer_author.id, site=site)
    answer = _create_test_answer(db, author_id=answer_author.id, question=question, site=site)

    suggest_edit_in = AnswerSuggestEditCreate(
        answer_uuid=answer.uuid,
        body_rich_text=RichText(
            source="Content",
            rendered_text="Content",
            editor="tiptap",
        ),
    )

    suggest_edit = crud.answer_suggest_edit.create_with_author(
        db, obj_in=suggest_edit_in, author_id=suggester.id, answer=answer
    )

    assert suggest_edit.status == "pending"

    updated = crud.answer_suggest_edit.update(
        db, db_obj=suggest_edit, obj_in=AnswerSuggestEditUpdate(status="accepted")
    )

    assert updated.status == "accepted"


def test_update_answer_suggest_edit_status_to_rejected(db: Session) -> None:
    """Test updating answer suggest edit status to rejected."""
    moderator = _create_test_user(db)
    answer_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    question = _create_test_question(db, author_id=answer_author.id, site=site)
    answer = _create_test_answer(db, author_id=answer_author.id, question=question, site=site)

    suggest_edit_in = AnswerSuggestEditCreate(
        answer_uuid=answer.uuid,
        body_rich_text=RichText(
            source="Content",
            rendered_text="Content",
            editor="tiptap",
        ),
    )

    suggest_edit = crud.answer_suggest_edit.create_with_author(
        db, obj_in=suggest_edit_in, author_id=suggester.id, answer=answer
    )

    updated = crud.answer_suggest_edit.update(
        db, db_obj=suggest_edit, obj_in=AnswerSuggestEditUpdate(status="rejected")
    )

    assert updated.status == "rejected"


def test_update_answer_suggest_edit_status_to_retracted(db: Session) -> None:
    """Test updating answer suggest edit status to retracted."""
    moderator = _create_test_user(db)
    answer_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    question = _create_test_question(db, author_id=answer_author.id, site=site)
    answer = _create_test_answer(db, author_id=answer_author.id, question=question, site=site)

    suggest_edit_in = AnswerSuggestEditCreate(
        answer_uuid=answer.uuid,
        body_rich_text=RichText(
            source="Content",
            rendered_text="Content",
            editor="tiptap",
        ),
    )

    suggest_edit = crud.answer_suggest_edit.create_with_author(
        db, obj_in=suggest_edit_in, author_id=suggester.id, answer=answer
    )

    updated = crud.answer_suggest_edit.update(
        db, db_obj=suggest_edit, obj_in=AnswerSuggestEditUpdate(status="retracted")
    )

    assert updated.status == "retracted"


def test_answer_suggest_edit_timestamps(db: Session) -> None:
    """Test that answer suggest edits have correct timestamps."""
    moderator = _create_test_user(db)
    answer_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    question = _create_test_question(db, author_id=answer_author.id, site=site)
    answer = _create_test_answer(db, author_id=answer_author.id, question=question, site=site)

    before_create = datetime.datetime.now(tz=datetime.timezone.utc)

    suggest_edit_in = AnswerSuggestEditCreate(
        answer_uuid=answer.uuid,
        body_rich_text=RichText(
            source="Content",
            rendered_text="Content",
            editor="tiptap",
        ),
    )

    suggest_edit = crud.answer_suggest_edit.create_with_author(
        db, obj_in=suggest_edit_in, author_id=suggester.id, answer=answer
    )

    after_create = datetime.datetime.now(tz=datetime.timezone.utc)

    assert suggest_edit.created_at is not None
    assert before_create <= suggest_edit.created_at <= after_create


def test_multiple_suggest_edits_for_same_answer(db: Session) -> None:
    """Test that multiple users can suggest edits for the same answer."""
    moderator = _create_test_user(db)
    answer_author = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    question = _create_test_question(db, author_id=answer_author.id, site=site)
    answer = _create_test_answer(db, author_id=answer_author.id, question=question, site=site)

    suggest_edits = []
    for i in range(3):
        suggester = _create_test_user(db)
        suggest_edit_in = AnswerSuggestEditCreate(
            answer_uuid=answer.uuid,
            body_rich_text=RichText(
                source=f"Suggestion {i}",
                rendered_text=f"Suggestion {i}",
                editor="tiptap",
            ),
            comment=f"Edit suggestion {i}",
        )
        suggest_edit = crud.answer_suggest_edit.create_with_author(
            db, obj_in=suggest_edit_in, author_id=suggester.id, answer=answer
        )
        suggest_edits.append(suggest_edit)

    assert len(suggest_edits) == 3
    assert all(se.answer_id == answer.id for se in suggest_edits)


def test_same_user_multiple_suggest_edits(db: Session) -> None:
    """Test that the same user can suggest multiple edits for an answer."""
    moderator = _create_test_user(db)
    answer_author = _create_test_user(db)
    suggester = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)
    question = _create_test_question(db, author_id=answer_author.id, site=site)
    answer = _create_test_answer(db, author_id=answer_author.id, question=question, site=site)

    suggest_edits = []
    for i in range(2):
        suggest_edit_in = AnswerSuggestEditCreate(
            answer_uuid=answer.uuid,
            body_rich_text=RichText(
                source=f"Revision {i}",
                rendered_text=f"Revision {i}",
                editor="tiptap",
            ),
        )
        suggest_edit = crud.answer_suggest_edit.create_with_author(
            db, obj_in=suggest_edit_in, author_id=suggester.id, answer=answer
        )
        suggest_edits.append(suggest_edit)

    assert len(suggest_edits) == 2
    assert all(se.author_id == suggester.id for se in suggest_edits)
