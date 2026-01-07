import asyncio
from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.schemas.comment import CommentCreate, CommentUpdate
from chafan_core.app.schemas.question import QuestionCreate
from chafan_core.app.schemas.richtext import RichText
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


def _create_test_question(db: Session, author_id: int, site_id: int):
    """Helper to create a test question."""
    question_in = QuestionCreate(
        site_uuid=crud.site.get(db, id=site_id).uuid,
        title=f"Test Question {random_short_lower_string()}",
    )
    return crud.question.create_with_author(db, obj_in=question_in, author_id=author_id)


def _noop_check_site(site: models.Site) -> None:
    """No-op check_site callback for testing."""
    pass


def test_create_comment_on_question(db: Session) -> None:
    """Test creating a comment on a question."""
    user = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=user.id, site_id=site.id)

    comment_in = CommentCreate(
        content=RichText(
            source="Test comment content",
            rendered_text="Test comment content",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
    )

    comment = crud.comment.create_with_author(
        db,
        obj_in=comment_in,
        author_id=user.id,
        check_site=_noop_check_site,
    )

    assert comment is not None
    assert comment.author_id == user.id
    assert comment.question_id == question.id
    assert comment.site_id == site.id
    assert comment.body == "Test comment content"
    assert comment.uuid is not None
    assert comment.is_deleted is False


def test_get_comment_by_uuid(db: Session) -> None:
    """Test retrieving a comment by UUID."""
    user = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=user.id, site_id=site.id)

    comment_in = CommentCreate(
        content=RichText(
            source="Test comment for UUID lookup",
            rendered_text="Test comment for UUID lookup",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
    )

    comment = crud.comment.create_with_author(
        db,
        obj_in=comment_in,
        author_id=user.id,
        check_site=_noop_check_site,
    )

    retrieved_comment = crud.comment.get_by_uuid(db, uuid=comment.uuid)
    assert retrieved_comment is not None
    assert retrieved_comment.id == comment.id
    assert retrieved_comment.uuid == comment.uuid


def test_comment_upvote(db: Session) -> None:
    """Test upvoting a comment."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=author.id, site_id=site.id)

    comment_in = CommentCreate(
        content=RichText(
            source="Test comment for upvote",
            rendered_text="Test comment for upvote",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
    )

    comment = crud.comment.create_with_author(
        db,
        obj_in=comment_in,
        author_id=author.id,
        check_site=_noop_check_site,
    )

    initial_upvotes = comment.upvotes_count

    # Upvote the comment
    updated_comment = crud.comment.upvote(db, db_obj=comment, voter=voter)
    assert updated_comment.upvotes_count == initial_upvotes + 1

    # Upvoting again should not increase count (idempotent)
    updated_comment = crud.comment.upvote(db, db_obj=comment, voter=voter)
    assert updated_comment.upvotes_count == initial_upvotes + 1


def test_comment_cancel_upvote(db: Session) -> None:
    """Test canceling an upvote on a comment."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=author.id, site_id=site.id)

    comment_in = CommentCreate(
        content=RichText(
            source="Test comment for cancel upvote",
            rendered_text="Test comment for cancel upvote",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
    )

    comment = crud.comment.create_with_author(
        db,
        obj_in=comment_in,
        author_id=author.id,
        check_site=_noop_check_site,
    )

    # First upvote
    comment = crud.comment.upvote(db, db_obj=comment, voter=voter)
    upvotes_after_upvote = comment.upvotes_count

    # Cancel upvote
    comment = crud.comment.cancel_upvote(db, db_obj=comment, voter=voter)
    assert comment.upvotes_count == upvotes_after_upvote - 1

    # Canceling again should not decrease count
    comment = crud.comment.cancel_upvote(db, db_obj=comment, voter=voter)
    assert comment.upvotes_count == upvotes_after_upvote - 1


def test_comment_reupvote_after_cancel(db: Session) -> None:
    """Test re-upvoting a comment after canceling."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=author.id, site_id=site.id)

    comment_in = CommentCreate(
        content=RichText(
            source="Test comment for reupvote",
            rendered_text="Test comment for reupvote",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
    )

    comment = crud.comment.create_with_author(
        db,
        obj_in=comment_in,
        author_id=author.id,
        check_site=_noop_check_site,
    )

    # Upvote
    comment = crud.comment.upvote(db, db_obj=comment, voter=voter)
    upvotes_after_first_upvote = comment.upvotes_count

    # Cancel
    comment = crud.comment.cancel_upvote(db, db_obj=comment, voter=voter)
    assert comment.upvotes_count == upvotes_after_first_upvote - 1

    # Re-upvote (reactivate cancelled upvote)
    comment = crud.comment.upvote(db, db_obj=comment, voter=voter)
    assert comment.upvotes_count == upvotes_after_first_upvote


def test_delete_forever(db: Session) -> None:
    """Test permanently deleting a comment."""
    user = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=user.id, site_id=site.id)

    comment_in = CommentCreate(
        content=RichText(
            source="Comment to be deleted",
            rendered_text="Comment to be deleted",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
    )

    comment = crud.comment.create_with_author(
        db,
        obj_in=comment_in,
        author_id=user.id,
        check_site=_noop_check_site,
    )

    crud.comment.delete_forever(db, comment=comment)

    # Refresh to get updated state
    db.refresh(comment)

    assert comment.is_deleted is True
    assert comment.body == "[DELETED]"
    assert comment.body_text == "[DELETED]"


def test_get_all_valid(db: Session) -> None:
    """Test getting all valid (not deleted) comments."""
    user = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=user.id, site_id=site.id)

    # Create a normal comment
    normal_comment_in = CommentCreate(
        content=RichText(
            source="Normal comment",
            rendered_text="Normal comment",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
    )

    normal_comment = crud.comment.create_with_author(
        db,
        obj_in=normal_comment_in,
        author_id=user.id,
        check_site=_noop_check_site,
    )

    # Create a comment and then delete it
    deleted_comment_in = CommentCreate(
        content=RichText(
            source="Comment to delete",
            rendered_text="Comment to delete",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
    )

    deleted_comment = crud.comment.create_with_author(
        db,
        obj_in=deleted_comment_in,
        author_id=user.id,
        check_site=_noop_check_site,
    )
    crud.comment.delete_forever(db, comment=deleted_comment)

    all_valid = crud.comment.get_all_valid(db)
    valid_ids = [c.id for c in all_valid]

    assert normal_comment.id in valid_ids
    assert deleted_comment.id not in valid_ids


def test_get_all(db: Session) -> None:
    """Test getting all comments including deleted ones."""
    initial_count = len(crud.comment.get_all(db))

    user = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=user.id, site_id=site.id)

    comment_in = CommentCreate(
        content=RichText(
            source="Comment for get_all test",
            rendered_text="Comment for get_all test",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
    )

    crud.comment.create_with_author(
        db,
        obj_in=comment_in,
        author_id=user.id,
        check_site=_noop_check_site,
    )

    all_comments = crud.comment.get_all(db)
    assert len(all_comments) == initial_count + 1


def test_create_reply_comment(db: Session) -> None:
    """Test creating a reply to a comment."""
    user = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=user.id, site_id=site.id)

    # Create parent comment
    parent_comment_in = CommentCreate(
        content=RichText(
            source="Parent comment",
            rendered_text="Parent comment",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
    )

    parent_comment = crud.comment.create_with_author(
        db,
        obj_in=parent_comment_in,
        author_id=user.id,
        check_site=_noop_check_site,
    )

    # Create reply comment
    reply_comment_in = CommentCreate(
        content=RichText(
            source="Reply comment",
            rendered_text="Reply comment",
            editor="tiptap",
        ),
        parent_comment_uuid=parent_comment.uuid,
    )

    reply_comment = crud.comment.create_with_author(
        db,
        obj_in=reply_comment_in,
        author_id=user.id,
        check_site=_noop_check_site,
    )

    assert reply_comment is not None
    assert reply_comment.parent_comment_id == parent_comment.id
    assert reply_comment.body == "Reply comment"


def test_get_comment_by_uuid_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get_by_uuid returns None for non-existent comment."""
    result = crud.comment.get_by_uuid(db, uuid="nonexistent-comment-uuid")
    assert result is None


def test_comment_shared_to_timeline(db: Session) -> None:
    """Test creating a comment with shared_to_timeline flag."""
    user = _create_test_user(db)
    site = _create_test_site(db)
    question = _create_test_question(db, author_id=user.id, site_id=site.id)

    comment_in = CommentCreate(
        content=RichText(
            source="Comment shared to timeline",
            rendered_text="Comment shared to timeline",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
        shared_to_timeline=True,
    )

    comment = crud.comment.create_with_author(
        db,
        obj_in=comment_in,
        author_id=user.id,
        check_site=_noop_check_site,
    )

    assert comment is not None
    assert comment.shared_to_timeline is True
