from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.topic import TopicCreate, TopicUpdate
from chafan_core.tests.utils.utils import random_short_lower_string


def test_create_topic(db: Session) -> None:
    """Test creating a topic."""
    topic_in = TopicCreate(name=f"Test Topic {random_short_lower_string()}")

    topic = crud.topic.create(db, obj_in=topic_in)

    assert topic is not None
    assert topic.name == topic_in.name
    assert topic.uuid is not None


def test_get_topic_by_name(db: Session) -> None:
    """Test retrieving a topic by name."""
    name = f"Unique Topic {random_short_lower_string()}"
    topic_in = TopicCreate(name=name)

    topic = crud.topic.create(db, obj_in=topic_in)

    retrieved_topic = crud.topic.get_by_name(db, name=name)
    assert retrieved_topic is not None
    assert retrieved_topic.id == topic.id
    assert retrieved_topic.name == name


def test_get_topic_by_uuid(db: Session) -> None:
    """Test retrieving a topic by UUID."""
    topic_in = TopicCreate(name=f"Topic for UUID lookup {random_short_lower_string()}")

    topic = crud.topic.create(db, obj_in=topic_in)

    retrieved_topic = crud.topic.get_by_uuid(db, uuid=topic.uuid)
    assert retrieved_topic is not None
    assert retrieved_topic.id == topic.id
    assert retrieved_topic.uuid == topic.uuid


def test_get_or_create_creates_new_topic(db: Session) -> None:
    """Test get_or_create creates a new topic when it doesn't exist."""
    name = f"New Topic {random_short_lower_string()}"

    # Verify topic doesn't exist
    assert crud.topic.get_by_name(db, name=name) is None

    # Get or create should create it
    topic = crud.topic.get_or_create(db, name=name)

    assert topic is not None
    assert topic.name == name
    assert topic.uuid is not None

    # Verify it now exists
    assert crud.topic.get_by_name(db, name=name) is not None


def test_get_or_create_returns_existing_topic(db: Session) -> None:
    """Test get_or_create returns existing topic when it exists."""
    name = f"Existing Topic {random_short_lower_string()}"

    # Create the topic first
    original_topic = crud.topic.create(db, obj_in=TopicCreate(name=name))

    # Get or create should return the existing topic
    topic = crud.topic.get_or_create(db, name=name)

    assert topic is not None
    assert topic.id == original_topic.id
    assert topic.uuid == original_topic.uuid


def test_get_category_topics(db: Session) -> None:
    """Test getting all category topics."""
    # Create a regular topic
    regular_topic_in = TopicCreate(name=f"Regular Topic {random_short_lower_string()}")
    regular_topic = crud.topic.create(db, obj_in=regular_topic_in)

    # Create a category topic
    category_topic_in = TopicCreate(name=f"Category Topic {random_short_lower_string()}")
    category_topic = crud.topic.create(db, obj_in=category_topic_in)
    crud.topic.update(db, db_obj=category_topic, obj_in={"is_category": True})

    category_topics = crud.topic.get_category_topics(db)
    category_ids = [t.id for t in category_topics]

    assert category_topic.id in category_ids
    assert regular_topic.id not in category_ids


def test_update_topic(db: Session) -> None:
    """Test updating a topic."""
    topic_in = TopicCreate(name=f"Topic to update {random_short_lower_string()}")
    topic = crud.topic.create(db, obj_in=topic_in)

    # Update description
    new_description = "Updated description"
    crud.topic.update(db, db_obj=topic, obj_in={"description": new_description})

    db.refresh(topic)
    assert topic.description == new_description


def test_get_topic_by_name_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get_by_name returns None for non-existent topic."""
    result = crud.topic.get_by_name(db, name="Nonexistent Topic Name")
    assert result is None


def test_get_topic_by_uuid_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get_by_uuid returns None for non-existent topic."""
    result = crud.topic.get_by_uuid(db, uuid="nonexistent-uuid")
    assert result is None


def test_get_topic(db: Session) -> None:
    """Test getting a topic by ID."""
    topic_in = TopicCreate(name=f"Topic for get {random_short_lower_string()}")
    topic = crud.topic.create(db, obj_in=topic_in)

    retrieved_topic = crud.topic.get(db, id=topic.id)
    assert retrieved_topic is not None
    assert retrieved_topic.id == topic.id


def test_multiple_category_topics(db: Session) -> None:
    """Test that multiple category topics can exist."""
    # Create multiple category topics
    category1_in = TopicCreate(name=f"Category 1 {random_short_lower_string()}")
    category1 = crud.topic.create(db, obj_in=category1_in)
    crud.topic.update(db, db_obj=category1, obj_in={"is_category": True})

    category2_in = TopicCreate(name=f"Category 2 {random_short_lower_string()}")
    category2 = crud.topic.create(db, obj_in=category2_in)
    crud.topic.update(db, db_obj=category2, obj_in={"is_category": True})

    category_topics = crud.topic.get_category_topics(db)
    category_ids = [t.id for t in category_topics]

    assert category1.id in category_ids
    assert category2.id in category_ids


def test_get_all_topics(db: Session) -> None:
    """Test getting all topics."""
    initial_count = len(crud.topic.get_all(db))

    topic_in = TopicCreate(name=f"Topic for get_all {random_short_lower_string()}")
    crud.topic.create(db, obj_in=topic_in)

    all_topics = crud.topic.get_all(db)
    assert len(all_topics) == initial_count + 1


def test_topic_uuid_is_unique(db: Session) -> None:
    """Test that each topic gets a unique UUID."""
    topic1_in = TopicCreate(name=f"Topic 1 {random_short_lower_string()}")
    topic1 = crud.topic.create(db, obj_in=topic1_in)

    topic2_in = TopicCreate(name=f"Topic 2 {random_short_lower_string()}")
    topic2 = crud.topic.create(db, obj_in=topic2_in)

    assert topic1.uuid != topic2.uuid
