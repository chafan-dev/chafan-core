import asyncio
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.channel import ChannelCreate
from chafan_core.app.schemas.user import UserCreate
from chafan_core.app.models.channel import Channel
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


def _create_basic_channel(db: Session, admin_id: int, private_with_user_id: int = None):
    """Helper to create a basic channel directly."""
    channel = Channel(
        name=f"Test Channel {random_short_lower_string()}",
        admin_id=admin_id,
        is_private=private_with_user_id is not None,
        private_with_user_id=private_with_user_id,
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


def test_add_user_to_channel(db: Session) -> None:
    """Test adding a user to a channel."""
    admin = _create_test_user(db)
    user = _create_test_user(db)

    channel = _create_basic_channel(db, admin_id=admin.id)

    # Initially channel should have no members or just the creator
    initial_member_count = len(channel.members)

    # Add user to channel
    updated_channel = crud.channel.add_user(db, db_obj=channel, user=user)

    assert len(updated_channel.members) == initial_member_count + 1
    member_ids = [m.id for m in updated_channel.members]
    assert user.id in member_ids


def test_add_multiple_users_to_channel(db: Session) -> None:
    """Test adding multiple users to a channel."""
    admin = _create_test_user(db)
    user1 = _create_test_user(db)
    user2 = _create_test_user(db)

    channel = _create_basic_channel(db, admin_id=admin.id)

    crud.channel.add_user(db, db_obj=channel, user=user1)
    crud.channel.add_user(db, db_obj=channel, user=user2)

    member_ids = [m.id for m in channel.members]
    assert user1.id in member_ids
    assert user2.id in member_ids


def test_get_or_create_private_channel_creates_new(db: Session) -> None:
    """Test get_or_create_private_channel_with creates a new channel when none exists."""
    host_user = _create_test_user(db)
    with_user = _create_test_user(db)

    channel_in = ChannelCreate(
        private_with_user_uuid=with_user.uuid,
        subject=None,
    )

    channel = crud.channel.get_or_create_private_channel_with(
        db, host_user=host_user, with_user=with_user, obj_in=channel_in
    )

    assert channel is not None
    assert channel.is_private is True
    assert channel.admin_id == host_user.id
    assert channel.private_with_user_id == with_user.id
    # Both users should be members
    member_ids = [m.id for m in channel.members]
    assert host_user.id in member_ids
    assert with_user.id in member_ids


def test_get_or_create_private_channel_returns_existing(db: Session) -> None:
    """Test get_or_create_private_channel_with returns existing channel."""
    host_user = _create_test_user(db)
    with_user = _create_test_user(db)

    channel_in = ChannelCreate(
        private_with_user_uuid=with_user.uuid,
        subject=None,
    )

    # Create channel first time
    channel1 = crud.channel.get_or_create_private_channel_with(
        db, host_user=host_user, with_user=with_user, obj_in=channel_in
    )

    # Try to create again - should return same channel
    channel2 = crud.channel.get_or_create_private_channel_with(
        db, host_user=host_user, with_user=with_user, obj_in=channel_in
    )

    assert channel1.id == channel2.id


def test_get_or_create_private_channel_symmetric(db: Session) -> None:
    """Test get_or_create_private_channel_with is symmetric (order doesn't matter)."""
    user1 = _create_test_user(db)
    user2 = _create_test_user(db)

    channel_in1 = ChannelCreate(
        private_with_user_uuid=user2.uuid,
        subject=None,
    )

    channel_in2 = ChannelCreate(
        private_with_user_uuid=user1.uuid,
        subject=None,
    )

    # Create channel with user1 as host
    channel1 = crud.channel.get_or_create_private_channel_with(
        db, host_user=user1, with_user=user2, obj_in=channel_in1
    )

    # Try to get channel with user2 as host - should return same channel
    channel2 = crud.channel.get_or_create_private_channel_with(
        db, host_user=user2, with_user=user1, obj_in=channel_in2
    )

    assert channel1.id == channel2.id


def test_find_channel_returns_existing(db: Session) -> None:
    """Test find_channel returns an existing private channel."""
    host_user = _create_test_user(db)
    with_user = _create_test_user(db)

    channel_in = ChannelCreate(
        private_with_user_uuid=with_user.uuid,
        subject=None,
    )

    # Create channel
    created_channel = crud.channel.get_or_create_private_channel_with(
        db, host_user=host_user, with_user=with_user, obj_in=channel_in
    )

    # Find it
    found_channel = crud.channel.find_channel(
        db, admin_user=host_user, with_user=with_user, subject=None
    )

    assert found_channel is not None
    assert found_channel.id == created_channel.id


def test_find_channel_returns_none_when_not_exists(db: Session) -> None:
    """Test find_channel returns None when no matching channel exists."""
    user1 = _create_test_user(db)
    user2 = _create_test_user(db)

    found_channel = crud.channel.find_channel(
        db, admin_user=user1, with_user=user2, subject=None
    )

    assert found_channel is None


def test_get_channel_by_id(db: Session) -> None:
    """Test getting a channel by ID."""
    admin = _create_test_user(db)
    channel = _create_basic_channel(db, admin_id=admin.id)

    retrieved_channel = crud.channel.get(db, id=channel.id)
    assert retrieved_channel is not None
    assert retrieved_channel.id == channel.id


def test_get_channel_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent channel."""
    result = crud.channel.get(db, id=99999999)
    assert result is None


def test_private_channel_has_correct_flags(db: Session) -> None:
    """Test that private channels have correct privacy flags."""
    host_user = _create_test_user(db)
    with_user = _create_test_user(db)

    channel_in = ChannelCreate(
        private_with_user_uuid=with_user.uuid,
        subject=None,
    )

    channel = crud.channel.get_or_create_private_channel_with(
        db, host_user=host_user, with_user=with_user, obj_in=channel_in
    )

    assert channel.is_private is True
    assert channel.private_with_user_id == with_user.id
    assert channel.admin_id == host_user.id


def test_different_user_pairs_get_different_channels(db: Session) -> None:
    """Test that different user pairs get different channels."""
    user1 = _create_test_user(db)
    user2 = _create_test_user(db)
    user3 = _create_test_user(db)

    channel_in_1_2 = ChannelCreate(
        private_with_user_uuid=user2.uuid,
        subject=None,
    )

    channel_in_1_3 = ChannelCreate(
        private_with_user_uuid=user3.uuid,
        subject=None,
    )

    channel_1_2 = crud.channel.get_or_create_private_channel_with(
        db, host_user=user1, with_user=user2, obj_in=channel_in_1_2
    )

    channel_1_3 = crud.channel.get_or_create_private_channel_with(
        db, host_user=user1, with_user=user3, obj_in=channel_in_1_3
    )

    assert channel_1_2.id != channel_1_3.id
