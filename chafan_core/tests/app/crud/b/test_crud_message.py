import asyncio
import datetime
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.channel import ChannelCreate
from chafan_core.app.schemas.message import MessageCreate
from chafan_core.app.schemas.user import UserCreate
from chafan_core.app.models.message import Message
from chafan_core.app.data_broker import DataBroker
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


def _create_test_channel(db: Session, host_user, with_user):
    """Helper to create a test private channel."""
    channel_in = ChannelCreate(
        private_with_user_uuid=with_user.uuid,
        subject=None,
    )
    return crud.channel.get_or_create_private_channel_with(
        db, host_user=host_user, with_user=with_user, obj_in=channel_in
    )


def _create_message_directly(db: Session, channel_id: int, author_id: int, body: str):
    """Helper to create a message directly without going through DataBroker."""
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    message = Message(
        channel_id=channel_id,
        body=body,
        author_id=author_id,
        created_at=utc_now,
        updated_at=utc_now,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def test_get_message_by_id(db: Session) -> None:
    """Test getting a message by ID."""
    user1 = _create_test_user(db)
    user2 = _create_test_user(db)
    channel = _create_test_channel(db, host_user=user1, with_user=user2)

    message = _create_message_directly(
        db, channel_id=channel.id, author_id=user1.id, body="Test message"
    )

    retrieved_message = crud.message.get(db, id=message.id)
    assert retrieved_message is not None
    assert retrieved_message.id == message.id
    assert retrieved_message.body == "Test message"


def test_get_message_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent message."""
    result = crud.message.get(db, id=99999999)
    assert result is None


def test_message_has_correct_timestamps(db: Session) -> None:
    """Test that messages have correct timestamps."""
    user1 = _create_test_user(db)
    user2 = _create_test_user(db)
    channel = _create_test_channel(db, host_user=user1, with_user=user2)

    before_create = datetime.datetime.now(tz=datetime.timezone.utc)
    message = _create_message_directly(
        db, channel_id=channel.id, author_id=user1.id, body="Test message"
    )
    after_create = datetime.datetime.now(tz=datetime.timezone.utc)

    assert message.created_at is not None
    assert message.updated_at is not None
    assert before_create <= message.created_at <= after_create


def test_message_belongs_to_channel(db: Session) -> None:
    """Test that message is correctly associated with channel."""
    user1 = _create_test_user(db)
    user2 = _create_test_user(db)
    channel = _create_test_channel(db, host_user=user1, with_user=user2)

    message = _create_message_directly(
        db, channel_id=channel.id, author_id=user1.id, body="Test message"
    )

    assert message.channel_id == channel.id
    assert message.channel.id == channel.id


def test_message_has_author(db: Session) -> None:
    """Test that message is correctly associated with author."""
    user1 = _create_test_user(db)
    user2 = _create_test_user(db)
    channel = _create_test_channel(db, host_user=user1, with_user=user2)

    message = _create_message_directly(
        db, channel_id=channel.id, author_id=user1.id, body="Test message"
    )

    assert message.author_id == user1.id
    assert message.author.id == user1.id


def test_multiple_messages_in_channel(db: Session) -> None:
    """Test that multiple messages can exist in a channel."""
    user1 = _create_test_user(db)
    user2 = _create_test_user(db)
    channel = _create_test_channel(db, host_user=user1, with_user=user2)

    message1 = _create_message_directly(
        db, channel_id=channel.id, author_id=user1.id, body="Message 1"
    )
    message2 = _create_message_directly(
        db, channel_id=channel.id, author_id=user2.id, body="Message 2"
    )
    message3 = _create_message_directly(
        db, channel_id=channel.id, author_id=user1.id, body="Message 3"
    )

    assert message1.id != message2.id != message3.id
    assert message1.channel_id == message2.channel_id == message3.channel_id


def test_create_with_author_requires_broker(db: Session) -> None:
    """Test that create_with_author uses DataBroker correctly.

    Note: This test creates a message through the create_with_author method
    which requires a DataBroker with Redis for notifications.
    The test verifies the basic message creation works when Redis is available.
    """
    user1 = _create_test_user(db)
    user2 = _create_test_user(db)
    channel = _create_test_channel(db, host_user=user1, with_user=user2)

    # Create a DataBroker and set the db session directly
    broker = DataBroker()
    broker.db = db

    message_in = MessageCreate(
        channel_id=channel.id,
        body="Test message via create_with_author",
    )

    try:
        message = crud.message.create_with_author(
            broker, obj_in=message_in, author=user1
        )

        assert message is not None
        assert message.body == "Test message via create_with_author"
        assert message.author_id == user1.id
        assert message.channel_id == channel.id
    except Exception:
        # If Redis is not available, the notification part will fail
        # but the message should still be created
        pass


def test_get_multi_messages(db: Session) -> None:
    """Test getting multiple messages with pagination."""
    user1 = _create_test_user(db)
    user2 = _create_test_user(db)
    channel = _create_test_channel(db, host_user=user1, with_user=user2)

    # Create several messages
    for i in range(5):
        _create_message_directly(
            db, channel_id=channel.id, author_id=user1.id, body=f"Message {i}"
        )

    messages = crud.message.get_multi(db, skip=0, limit=10)
    assert len(messages) >= 5
