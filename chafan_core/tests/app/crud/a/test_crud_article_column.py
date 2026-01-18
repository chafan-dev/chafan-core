import asyncio
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.article_column import (
    ArticleColumnCreate,
    ArticleColumnUpdate,
)
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


def test_create_article_column_with_owner(db: Session) -> None:
    """Test creating an article column with an owner."""
    user = _create_test_user(db)

    column_in = ArticleColumnCreate(
        name=f"Test Column {random_short_lower_string()}",
        description="Test column description",
    )

    column = crud.article_column.create_with_owner(
        db, obj_in=column_in, owner_id=user.id
    )

    assert column is not None
    assert column.name == column_in.name
    assert column.description == column_in.description
    assert column.owner_id == user.id
    assert column.uuid is not None
    assert column.created_at is not None


def test_create_article_column_without_description(db: Session) -> None:
    """Test creating an article column without description."""
    user = _create_test_user(db)

    column_in = ArticleColumnCreate(
        name=f"Column No Desc {random_short_lower_string()}",
    )

    column = crud.article_column.create_with_owner(
        db, obj_in=column_in, owner_id=user.id
    )

    assert column is not None
    assert column.name == column_in.name
    assert column.description is None


def test_get_article_column_by_uuid(db: Session) -> None:
    """Test retrieving an article column by UUID."""
    user = _create_test_user(db)

    column_in = ArticleColumnCreate(
        name=f"Column for UUID lookup {random_short_lower_string()}",
        description="Test column",
    )

    column = crud.article_column.create_with_owner(
        db, obj_in=column_in, owner_id=user.id
    )

    retrieved_column = crud.article_column.get_by_uuid(db, uuid=column.uuid)
    assert retrieved_column is not None
    assert retrieved_column.id == column.id
    assert retrieved_column.uuid == column.uuid


def test_get_article_column_by_id(db: Session) -> None:
    """Test retrieving an article column by ID."""
    user = _create_test_user(db)

    column_in = ArticleColumnCreate(
        name=f"Column for ID lookup {random_short_lower_string()}",
        description="Test column",
    )

    column = crud.article_column.create_with_owner(
        db, obj_in=column_in, owner_id=user.id
    )

    retrieved_column = crud.article_column.get(db, id=column.id)
    assert retrieved_column is not None
    assert retrieved_column.id == column.id


def test_update_article_column(db: Session) -> None:
    """Test updating an article column."""
    user = _create_test_user(db)

    column_in = ArticleColumnCreate(
        name=f"Original Column Name {random_short_lower_string()}",
        description="Original description",
    )

    column = crud.article_column.create_with_owner(
        db, obj_in=column_in, owner_id=user.id
    )

    # Update name and description
    new_name = f"Updated Column Name {random_short_lower_string()}"
    new_description = "Updated description"
    update_in = ArticleColumnUpdate(name=new_name, description=new_description)
    crud.article_column.update(db, db_obj=column, obj_in=update_in)

    db.refresh(column)
    assert column.name == new_name
    assert column.description == new_description


def test_update_article_column_partial(db: Session) -> None:
    """Test partial update of an article column."""
    user = _create_test_user(db)

    column_in = ArticleColumnCreate(
        name=f"Column for partial update {random_short_lower_string()}",
        description="Original description",
    )

    column = crud.article_column.create_with_owner(
        db, obj_in=column_in, owner_id=user.id
    )

    original_name = column.name

    # Update only description
    new_description = "New description only"
    crud.article_column.update(
        db, db_obj=column, obj_in={"description": new_description}
    )

    db.refresh(column)
    assert column.name == original_name  # Name unchanged
    assert column.description == new_description


def test_user_can_have_multiple_article_columns(db: Session) -> None:
    """Test that a user can own multiple article columns."""
    user = _create_test_user(db)

    column1_in = ArticleColumnCreate(
        name=f"Column 1 {random_short_lower_string()}",
        description="First column",
    )
    column1 = crud.article_column.create_with_owner(
        db, obj_in=column1_in, owner_id=user.id
    )

    column2_in = ArticleColumnCreate(
        name=f"Column 2 {random_short_lower_string()}",
        description="Second column",
    )
    column2 = crud.article_column.create_with_owner(
        db, obj_in=column2_in, owner_id=user.id
    )

    # Both columns should exist with same owner
    assert column1.owner_id == user.id
    assert column2.owner_id == user.id
    assert column1.id != column2.id
    assert column1.uuid != column2.uuid


def test_different_users_can_have_article_columns(db: Session) -> None:
    """Test that different users can own article columns."""
    user1 = _create_test_user(db)
    user2 = _create_test_user(db)

    column1_in = ArticleColumnCreate(
        name=f"User1 Column {random_short_lower_string()}",
        description="User 1's column",
    )
    column1 = crud.article_column.create_with_owner(
        db, obj_in=column1_in, owner_id=user1.id
    )

    column2_in = ArticleColumnCreate(
        name=f"User2 Column {random_short_lower_string()}",
        description="User 2's column",
    )
    column2 = crud.article_column.create_with_owner(
        db, obj_in=column2_in, owner_id=user2.id
    )

    assert column1.owner_id == user1.id
    assert column2.owner_id == user2.id


def test_get_article_column_by_uuid_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get_by_uuid returns None for non-existent column."""
    result = crud.article_column.get_by_uuid(db, uuid="nonexistent-uuid")
    assert result is None


def test_get_article_column_returns_none_for_nonexistent_id(db: Session) -> None:
    """Test that get returns None for non-existent column ID."""
    result = crud.article_column.get(db, id=99999999)
    assert result is None


def test_get_all_article_columns(db: Session) -> None:
    """Test getting all article columns."""
    initial_count = len(crud.article_column.get_all(db))

    user = _create_test_user(db)

    column_in = ArticleColumnCreate(
        name=f"Column for get_all {random_short_lower_string()}",
        description="Test column",
    )

    crud.article_column.create_with_owner(db, obj_in=column_in, owner_id=user.id)

    all_columns = crud.article_column.get_all(db)
    assert len(all_columns) == initial_count + 1


def test_article_column_uuid_is_unique(db: Session) -> None:
    """Test that each article column gets a unique UUID."""
    user = _create_test_user(db)

    column1_in = ArticleColumnCreate(
        name=f"Column 1 {random_short_lower_string()}",
    )
    column1 = crud.article_column.create_with_owner(
        db, obj_in=column1_in, owner_id=user.id
    )

    column2_in = ArticleColumnCreate(
        name=f"Column 2 {random_short_lower_string()}",
    )
    column2 = crud.article_column.create_with_owner(
        db, obj_in=column2_in, owner_id=user.id
    )

    assert column1.uuid != column2.uuid


def test_article_column_created_at_is_set(db: Session) -> None:
    """Test that created_at timestamp is set on creation."""
    user = _create_test_user(db)

    column_in = ArticleColumnCreate(
        name=f"Column with timestamp {random_short_lower_string()}",
    )

    column = crud.article_column.create_with_owner(
        db, obj_in=column_in, owner_id=user.id
    )

    assert column.created_at is not None
