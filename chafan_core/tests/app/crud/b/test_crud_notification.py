import asyncio
import datetime
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.notification import NotificationCreate, NotificationUpdate
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


def _create_test_notification(
    db: Session, receiver_id: int, is_read: bool = False, is_delivered: bool = False
):
    """Helper to create a test notification."""
    notification_in = NotificationCreate(
        receiver_id=receiver_id,
        created_at=datetime.datetime.now(tz=datetime.timezone.utc),
        event_json='{"type": "test", "data": {}}',
    )
    notification = crud.notification.create(db, obj_in=notification_in)

    # Update is_read and is_delivered if needed
    if is_read or is_delivered:
        update_data = {}
        if is_read:
            update_data["is_read"] = True
        if is_delivered:
            update_data["is_delivered"] = True
        crud.notification.update(db, db_obj=notification, obj_in=update_data)
        db.refresh(notification)

    return notification


def test_create_notification(db: Session) -> None:
    """Test creating a notification."""
    user = _create_test_user(db)

    notification_in = NotificationCreate(
        receiver_id=user.id,
        created_at=datetime.datetime.now(tz=datetime.timezone.utc),
        event_json='{"type": "test_create", "data": {"message": "Hello"}}',
    )

    notification = crud.notification.create(db, obj_in=notification_in)

    assert notification is not None
    assert notification.receiver_id == user.id
    assert notification.is_read is False
    assert notification.is_delivered is False
    assert notification.event_json is not None
    assert notification.created_at is not None


def test_get_notification(db: Session) -> None:
    """Test retrieving a notification by ID."""
    user = _create_test_user(db)
    notification = _create_test_notification(db, receiver_id=user.id)

    retrieved_notification = crud.notification.get(db, id=notification.id)
    assert retrieved_notification is not None
    assert retrieved_notification.id == notification.id


def test_get_unread_notifications(db: Session) -> None:
    """Test getting unread notifications for a user."""
    user = _create_test_user(db)

    # Create unread notifications
    unread1 = _create_test_notification(db, receiver_id=user.id, is_read=False)
    unread2 = _create_test_notification(db, receiver_id=user.id, is_read=False)

    # Create a read notification
    read_notification = _create_test_notification(db, receiver_id=user.id, is_read=True)

    unread_notifications = crud.notification.get_unread(db, receiver_id=user.id)
    unread_ids = [n.id for n in unread_notifications]

    assert unread1.id in unread_ids
    assert unread2.id in unread_ids
    assert read_notification.id not in unread_ids


def test_get_read_notifications(db: Session) -> None:
    """Test getting read notifications for a user."""
    user = _create_test_user(db)

    # Create read notifications
    read1 = _create_test_notification(db, receiver_id=user.id, is_read=True)
    read2 = _create_test_notification(db, receiver_id=user.id, is_read=True)

    # Create an unread notification
    unread_notification = _create_test_notification(
        db, receiver_id=user.id, is_read=False
    )

    read_notifications = crud.notification.get_read(db, receiver_id=user.id)
    read_ids = [n.id for n in read_notifications]

    assert read1.id in read_ids
    assert read2.id in read_ids
    assert unread_notification.id not in read_ids


def test_get_undelivered_unread(db: Session) -> None:
    """Test getting undelivered and unread notifications."""
    user = _create_test_user(db)

    # Create undelivered, unread notification
    undelivered_unread = _create_test_notification(
        db, receiver_id=user.id, is_read=False, is_delivered=False
    )

    # Create delivered, unread notification
    delivered_unread = _create_test_notification(
        db, receiver_id=user.id, is_read=False, is_delivered=True
    )

    # Create undelivered, read notification
    undelivered_read = _create_test_notification(
        db, receiver_id=user.id, is_read=True, is_delivered=False
    )

    undelivered_unread_notifications = list(
        crud.notification.get_undelivered_unread(db)
    )
    ids = [n.id for n in undelivered_unread_notifications]

    assert undelivered_unread.id in ids
    assert delivered_unread.id not in ids
    assert undelivered_read.id not in ids


def test_update_notification_mark_as_read(db: Session) -> None:
    """Test marking a notification as read."""
    user = _create_test_user(db)
    notification = _create_test_notification(db, receiver_id=user.id, is_read=False)

    assert notification.is_read is False

    update_in = NotificationUpdate(is_read=True)
    crud.notification.update(db, db_obj=notification, obj_in=update_in)

    db.refresh(notification)
    assert notification.is_read is True


def test_get_unread_for_different_users(db: Session) -> None:
    """Test that get_unread only returns notifications for the specified user."""
    user1 = _create_test_user(db)
    user2 = _create_test_user(db)

    # Create notifications for user1
    user1_notification = _create_test_notification(
        db, receiver_id=user1.id, is_read=False
    )

    # Create notifications for user2
    user2_notification = _create_test_notification(
        db, receiver_id=user2.id, is_read=False
    )

    # Get unread for user1
    user1_unread = crud.notification.get_unread(db, receiver_id=user1.id)
    user1_unread_ids = [n.id for n in user1_unread]

    assert user1_notification.id in user1_unread_ids
    assert user2_notification.id not in user1_unread_ids


def test_get_read_limited_to_50(db: Session) -> None:
    """Test that get_read returns at most 50 notifications."""
    user = _create_test_user(db)

    # Create 55 read notifications
    for _ in range(55):
        _create_test_notification(db, receiver_id=user.id, is_read=True)

    read_notifications = crud.notification.get_read(db, receiver_id=user.id)

    # Should be limited to 50
    assert len(read_notifications) <= 50


def test_unread_ordered_by_created_at_desc(db: Session) -> None:
    """Test that unread notifications are ordered by created_at descending."""
    user = _create_test_user(db)

    # Create notifications with different timestamps
    older_notification_in = NotificationCreate(
        receiver_id=user.id,
        created_at=datetime.datetime.now(tz=datetime.timezone.utc)
        - datetime.timedelta(hours=1),
        event_json='{"type": "older", "data": {}}',
    )
    older_notification = crud.notification.create(db, obj_in=older_notification_in)

    newer_notification_in = NotificationCreate(
        receiver_id=user.id,
        created_at=datetime.datetime.now(tz=datetime.timezone.utc),
        event_json='{"type": "newer", "data": {}}',
    )
    newer_notification = crud.notification.create(db, obj_in=newer_notification_in)

    unread_notifications = crud.notification.get_unread(db, receiver_id=user.id)

    # Find positions of our test notifications
    ids = [n.id for n in unread_notifications]
    if newer_notification.id in ids and older_notification.id in ids:
        newer_index = ids.index(newer_notification.id)
        older_index = ids.index(older_notification.id)
        # Newer should come before older (descending order)
        assert newer_index < older_index


def test_update_notification_mark_as_delivered(db: Session) -> None:
    """Test marking a notification as delivered."""
    user = _create_test_user(db)
    notification = _create_test_notification(
        db, receiver_id=user.id, is_delivered=False
    )

    assert notification.is_delivered is False

    crud.notification.update(db, db_obj=notification, obj_in={"is_delivered": True})

    db.refresh(notification)
    assert notification.is_delivered is True


def test_get_notification_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent notification."""
    result = crud.notification.get(db, id=99999999)
    assert result is None
