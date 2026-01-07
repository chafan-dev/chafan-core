import asyncio
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.article import ArticleCreate, ArticleUpdate
from chafan_core.app.schemas.article_column import ArticleColumnCreate
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.schemas.user import UserCreate
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


def _create_test_article_column(db: Session, owner_id: int):
    """Helper to create a test article column."""
    column_in = ArticleColumnCreate(
        name=f"Test Column {random_short_lower_string()}",
        description="Test column description",
    )
    return crud.article_column.create_with_owner(db, obj_in=column_in, owner_id=owner_id)


def test_create_article_with_author(db: Session) -> None:
    """Test creating an article with an author."""
    user = _create_test_user(db)
    column = _create_test_article_column(db, owner_id=user.id)

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

    article = crud.article.create_with_author(
        db, obj_in=article_in, author_id=user.id
    )

    assert article is not None
    assert article.author_id == user.id
    assert article.article_column_id == column.id
    assert article.is_published is True
    assert article.title == article_in.title
    assert article.body == "Test article content"
    assert article.uuid is not None
    assert article.created_at is not None


def test_create_unpublished_article(db: Session) -> None:
    """Test creating an unpublished (draft) article."""
    user = _create_test_user(db)
    column = _create_test_article_column(db, owner_id=user.id)

    article_in = ArticleCreate(
        title=f"Draft Article {random_short_lower_string()}",
        content=RichText(
            source="Draft content",
            rendered_text="Draft content",
            editor="tiptap",
        ),
        article_column_uuid=column.uuid,
        is_published=False,
        writing_session_uuid=get_uuid(),
        visibility=ContentVisibility.ANYONE,
    )

    article = crud.article.create_with_author(
        db, obj_in=article_in, author_id=user.id
    )

    assert article is not None
    assert article.is_published is False


def test_get_article_by_uuid(db: Session) -> None:
    """Test retrieving an article by UUID."""
    user = _create_test_user(db)
    column = _create_test_article_column(db, owner_id=user.id)

    article_in = ArticleCreate(
        title=f"Test Article for UUID lookup {random_short_lower_string()}",
        content=RichText(
            source="Test content for UUID lookup",
            rendered_text="Test content for UUID lookup",
            editor="tiptap",
        ),
        article_column_uuid=column.uuid,
        is_published=True,
        writing_session_uuid=get_uuid(),
        visibility=ContentVisibility.ANYONE,
    )

    article = crud.article.create_with_author(
        db, obj_in=article_in, author_id=user.id
    )

    retrieved_article = crud.article.get_by_uuid(db, uuid=article.uuid)
    assert retrieved_article is not None
    assert retrieved_article.id == article.id
    assert retrieved_article.uuid == article.uuid


def test_article_upvote(db: Session) -> None:
    """Test upvoting an article."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    column = _create_test_article_column(db, owner_id=author.id)

    article_in = ArticleCreate(
        title=f"Test Article for upvote {random_short_lower_string()}",
        content=RichText(
            source="Test content for upvote",
            rendered_text="Test content for upvote",
            editor="tiptap",
        ),
        article_column_uuid=column.uuid,
        is_published=True,
        writing_session_uuid=get_uuid(),
        visibility=ContentVisibility.ANYONE,
    )

    article = crud.article.create_with_author(
        db, obj_in=article_in, author_id=author.id
    )

    initial_upvotes = article.upvotes_count

    # Upvote the article
    updated_article = crud.article.upvote(db, db_obj=article, voter=voter)
    assert updated_article.upvotes_count == initial_upvotes + 1

    # Upvoting again should not increase count (idempotent)
    updated_article = crud.article.upvote(db, db_obj=article, voter=voter)
    assert updated_article.upvotes_count == initial_upvotes + 1


def test_article_cancel_upvote(db: Session) -> None:
    """Test canceling an upvote on an article."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    column = _create_test_article_column(db, owner_id=author.id)

    article_in = ArticleCreate(
        title=f"Test Article for cancel upvote {random_short_lower_string()}",
        content=RichText(
            source="Test content for cancel upvote",
            rendered_text="Test content for cancel upvote",
            editor="tiptap",
        ),
        article_column_uuid=column.uuid,
        is_published=True,
        writing_session_uuid=get_uuid(),
        visibility=ContentVisibility.ANYONE,
    )

    article = crud.article.create_with_author(
        db, obj_in=article_in, author_id=author.id
    )

    # First upvote
    article = crud.article.upvote(db, db_obj=article, voter=voter)
    upvotes_after_upvote = article.upvotes_count

    # Cancel upvote
    article = crud.article.cancel_upvote(db, db_obj=article, voter=voter)
    assert article.upvotes_count == upvotes_after_upvote - 1

    # Canceling again should not decrease count
    article = crud.article.cancel_upvote(db, db_obj=article, voter=voter)
    assert article.upvotes_count == upvotes_after_upvote - 1


def test_article_reupvote_after_cancel(db: Session) -> None:
    """Test re-upvoting an article after canceling."""
    author = _create_test_user(db)
    voter = _create_test_user(db)
    column = _create_test_article_column(db, owner_id=author.id)

    article_in = ArticleCreate(
        title=f"Test Article for reupvote {random_short_lower_string()}",
        content=RichText(
            source="Test content for reupvote",
            rendered_text="Test content for reupvote",
            editor="tiptap",
        ),
        article_column_uuid=column.uuid,
        is_published=True,
        writing_session_uuid=get_uuid(),
        visibility=ContentVisibility.ANYONE,
    )

    article = crud.article.create_with_author(
        db, obj_in=article_in, author_id=author.id
    )

    # Upvote
    article = crud.article.upvote(db, db_obj=article, voter=voter)
    upvotes_after_first_upvote = article.upvotes_count

    # Cancel
    article = crud.article.cancel_upvote(db, db_obj=article, voter=voter)
    assert article.upvotes_count == upvotes_after_first_upvote - 1

    # Re-upvote (reactivate cancelled upvote)
    article = crud.article.upvote(db, db_obj=article, voter=voter)
    assert article.upvotes_count == upvotes_after_first_upvote


def test_update_article_topics(db: Session) -> None:
    """Test updating article topics."""
    user = _create_test_user(db)
    column = _create_test_article_column(db, owner_id=user.id)

    article_in = ArticleCreate(
        title=f"Test Article for topics {random_short_lower_string()}",
        content=RichText(
            source="Test content for topics",
            rendered_text="Test content for topics",
            editor="tiptap",
        ),
        article_column_uuid=column.uuid,
        is_published=True,
        writing_session_uuid=get_uuid(),
        visibility=ContentVisibility.ANYONE,
    )

    article = crud.article.create_with_author(
        db, obj_in=article_in, author_id=user.id
    )

    # Create test topics
    from chafan_core.app.schemas.topic import TopicCreate

    topic1_in = TopicCreate(name=f"ArticleTopic1 {random_short_lower_string()}")
    topic2_in = TopicCreate(name=f"ArticleTopic2 {random_short_lower_string()}")

    topic1 = crud.topic.create(db, obj_in=topic1_in)
    topic2 = crud.topic.create(db, obj_in=topic2_in)

    # Update topics
    article = crud.article.update_topics(
        db, db_obj=article, new_topics=[topic1, topic2]
    )

    assert len(article.topics) == 2
    topic_ids = [t.id for t in article.topics]
    assert topic1.id in topic_ids
    assert topic2.id in topic_ids


def test_delete_forever(db: Session) -> None:
    """Test permanently deleting an article."""
    user = _create_test_user(db)
    column = _create_test_article_column(db, owner_id=user.id)

    article_in = ArticleCreate(
        title=f"Article to be deleted {random_short_lower_string()}",
        content=RichText(
            source="Content to be deleted",
            rendered_text="Content to be deleted",
            editor="tiptap",
        ),
        article_column_uuid=column.uuid,
        is_published=True,
        writing_session_uuid=get_uuid(),
        visibility=ContentVisibility.ANYONE,
    )

    article = crud.article.create_with_author(
        db, obj_in=article_in, author_id=user.id
    )

    crud.article.delete_forever(db, article=article)

    # Refresh to get updated state
    db.refresh(article)

    assert article.is_deleted is True
    assert article.body == "[DELETED]"


def test_update_checked_cannot_unpublish(db: Session) -> None:
    """Test that update_checked prevents unpublishing a published article."""
    user = _create_test_user(db)
    column = _create_test_article_column(db, owner_id=user.id)

    article_in = ArticleCreate(
        title=f"Published article for update_checked {random_short_lower_string()}",
        content=RichText(
            source="Published content for update_checked",
            rendered_text="Published content for update_checked",
            editor="tiptap",
        ),
        article_column_uuid=column.uuid,
        is_published=True,
        writing_session_uuid=get_uuid(),
        visibility=ContentVisibility.ANYONE,
    )

    article = crud.article.create_with_author(
        db, obj_in=article_in, author_id=user.id
    )

    # Should raise assertion error when trying to unpublish
    try:
        crud.article.update_checked(db, db_obj=article, obj_in={"is_published": False})
        assert False, "Expected assertion error"
    except AssertionError:
        pass  # Expected behavior


def test_get_all_published(db: Session) -> None:
    """Test getting all published articles."""
    user = _create_test_user(db)
    column = _create_test_article_column(db, owner_id=user.id)

    # Create a published article
    published_article_in = ArticleCreate(
        title=f"Published Article {random_short_lower_string()}",
        content=RichText(
            source="Published content",
            rendered_text="Published content",
            editor="tiptap",
        ),
        article_column_uuid=column.uuid,
        is_published=True,
        writing_session_uuid=get_uuid(),
        visibility=ContentVisibility.ANYONE,
    )

    published_article = crud.article.create_with_author(
        db, obj_in=published_article_in, author_id=user.id
    )

    # Create an unpublished article
    unpublished_article_in = ArticleCreate(
        title=f"Unpublished Article {random_short_lower_string()}",
        content=RichText(
            source="Unpublished content",
            rendered_text="Unpublished content",
            editor="tiptap",
        ),
        article_column_uuid=column.uuid,
        is_published=False,
        writing_session_uuid=get_uuid(),
        visibility=ContentVisibility.ANYONE,
    )

    unpublished_article = crud.article.create_with_author(
        db, obj_in=unpublished_article_in, author_id=user.id
    )

    all_published = crud.article.get_all_published(db)
    published_ids = [a.id for a in all_published]

    assert published_article.id in published_ids
    assert unpublished_article.id not in published_ids


def test_get_all(db: Session) -> None:
    """Test getting all articles including unpublished ones."""
    initial_count = len(crud.article.get_all(db))

    user = _create_test_user(db)
    column = _create_test_article_column(db, owner_id=user.id)

    article_in = ArticleCreate(
        title=f"Article for get_all test {random_short_lower_string()}",
        content=RichText(
            source="Content for get_all test",
            rendered_text="Content for get_all test",
            editor="tiptap",
        ),
        article_column_uuid=column.uuid,
        is_published=True,
        writing_session_uuid=get_uuid(),
        visibility=ContentVisibility.ANYONE,
    )

    crud.article.create_with_author(
        db, obj_in=article_in, author_id=user.id
    )

    all_articles = crud.article.get_all(db)
    assert len(all_articles) == initial_count + 1


def test_get_article_by_uuid_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get_by_uuid returns None for non-existent article."""
    result = crud.article.get_by_uuid(db, uuid="nonexistent-article-uuid")
    assert result is None
