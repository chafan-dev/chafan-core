import asyncio
import datetime
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.reward import RewardCreate
from chafan_core.app.schemas.user import UserCreate
from chafan_core.tests.utils.utils import (
    random_email,
    random_password,
    random_short_lower_string,
)


def _create_test_user(db: Session, initial_coins: int = 1000):
    """Helper to create a test user with initial coins."""
    user_in = UserCreate(
        email=random_email(),
        password=random_password(),
        handle=random_short_lower_string(),
    )
    user = asyncio.run(crud.user.create(db, obj_in=user_in))
    if initial_coins > 0:
        crud.user.update(db, db_obj=user, obj_in={"remaining_coins": initial_coins})
        db.refresh(user)
    return user


def test_create_reward_with_giver(db: Session) -> None:
    """Test creating a reward with a giver."""
    giver = _create_test_user(db, initial_coins=1000)
    receiver = _create_test_user(db, initial_coins=0)

    giver_initial_coins = giver.remaining_coins

    reward_in = RewardCreate(
        expired_after_days=30,
        receiver_uuid=receiver.uuid,
        coin_amount=100,
        note_to_receiver="Great work!",
    )

    reward = crud.reward.create_with_giver(db, obj_in=reward_in, giver=giver)

    assert reward is not None
    assert reward.giver_id == giver.id
    assert reward.receiver_id == receiver.id
    assert reward.coin_amount == 100
    assert reward.note_to_receiver == "Great work!"
    assert reward.created_at is not None
    assert reward.expired_at is not None

    # Giver's coins should be deducted
    db.refresh(giver)
    assert giver.remaining_coins == giver_initial_coins - 100


def test_reward_expiration_time(db: Session) -> None:
    """Test that reward expiration time is correctly set."""
    giver = _create_test_user(db, initial_coins=1000)
    receiver = _create_test_user(db)

    before_create = datetime.datetime.now(tz=datetime.timezone.utc)

    reward_in = RewardCreate(
        expired_after_days=30,
        receiver_uuid=receiver.uuid,
        coin_amount=50,
    )

    reward = crud.reward.create_with_giver(db, obj_in=reward_in, giver=giver)

    after_create = datetime.datetime.now(tz=datetime.timezone.utc)

    # Expiration should be about 30 days from now
    expected_min_expiry = before_create + datetime.timedelta(days=30)
    expected_max_expiry = after_create + datetime.timedelta(days=30)

    assert expected_min_expiry <= reward.expired_at <= expected_max_expiry


def test_reward_without_note(db: Session) -> None:
    """Test creating a reward without a note."""
    giver = _create_test_user(db, initial_coins=1000)
    receiver = _create_test_user(db)

    reward_in = RewardCreate(
        expired_after_days=7,
        receiver_uuid=receiver.uuid,
        coin_amount=25,
        note_to_receiver=None,
    )

    reward = crud.reward.create_with_giver(db, obj_in=reward_in, giver=giver)

    assert reward is not None
    assert reward.note_to_receiver is None


def test_get_reward_by_id(db: Session) -> None:
    """Test getting a reward by ID."""
    giver = _create_test_user(db, initial_coins=1000)
    receiver = _create_test_user(db)

    reward_in = RewardCreate(
        expired_after_days=30,
        receiver_uuid=receiver.uuid,
        coin_amount=100,
    )

    reward = crud.reward.create_with_giver(db, obj_in=reward_in, giver=giver)

    retrieved = crud.reward.get(db, id=reward.id)
    assert retrieved is not None
    assert retrieved.id == reward.id


def test_get_reward_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent reward."""
    result = crud.reward.get(db, id=99999999)
    assert result is None


def test_reward_deducts_coins_from_giver(db: Session) -> None:
    """Test that creating a reward correctly deducts coins from giver."""
    giver = _create_test_user(db, initial_coins=500)
    receiver = _create_test_user(db)

    reward_in = RewardCreate(
        expired_after_days=30,
        receiver_uuid=receiver.uuid,
        coin_amount=200,
    )

    crud.reward.create_with_giver(db, obj_in=reward_in, giver=giver)

    db.refresh(giver)
    assert giver.remaining_coins == 300


def test_multiple_rewards_from_same_giver(db: Session) -> None:
    """Test that a giver can give multiple rewards."""
    giver = _create_test_user(db, initial_coins=1000)

    rewards = []
    for i in range(3):
        receiver = _create_test_user(db)
        reward_in = RewardCreate(
            expired_after_days=30,
            receiver_uuid=receiver.uuid,
            coin_amount=100,
            note_to_receiver=f"Reward {i}",
        )
        reward = crud.reward.create_with_giver(db, obj_in=reward_in, giver=giver)
        rewards.append(reward)

    assert len(rewards) == 3

    # Giver should have 700 coins left (1000 - 3*100)
    db.refresh(giver)
    assert giver.remaining_coins == 700


def test_multiple_rewards_to_same_receiver(db: Session) -> None:
    """Test that a receiver can receive multiple rewards."""
    receiver = _create_test_user(db)

    rewards = []
    for _ in range(3):
        giver = _create_test_user(db, initial_coins=1000)
        reward_in = RewardCreate(
            expired_after_days=30,
            receiver_uuid=receiver.uuid,
            coin_amount=50,
        )
        reward = crud.reward.create_with_giver(db, obj_in=reward_in, giver=giver)
        rewards.append(reward)

    assert len(rewards) == 3
    assert all(r.receiver_id == receiver.id for r in rewards)


def test_reward_timestamps(db: Session) -> None:
    """Test that rewards have correct timestamps."""
    giver = _create_test_user(db, initial_coins=1000)
    receiver = _create_test_user(db)

    before_create = datetime.datetime.now(tz=datetime.timezone.utc)

    reward_in = RewardCreate(
        expired_after_days=30,
        receiver_uuid=receiver.uuid,
        coin_amount=100,
    )

    reward = crud.reward.create_with_giver(db, obj_in=reward_in, giver=giver)

    after_create = datetime.datetime.now(tz=datetime.timezone.utc)

    assert reward.created_at is not None
    assert before_create <= reward.created_at <= after_create


def test_different_expiration_periods(db: Session) -> None:
    """Test creating rewards with different expiration periods."""
    giver = _create_test_user(db, initial_coins=1000)
    receiver = _create_test_user(db)

    for days in [7, 14, 30]:
        before_create = datetime.datetime.now(tz=datetime.timezone.utc)

        reward_in = RewardCreate(
            expired_after_days=days,
            receiver_uuid=receiver.uuid,
            coin_amount=50,
        )

        reward = crud.reward.create_with_giver(db, obj_in=reward_in, giver=giver)

        expected_min = before_create + datetime.timedelta(days=days)
        expected_max = before_create + datetime.timedelta(days=days, seconds=5)

        assert expected_min <= reward.expired_at <= expected_max
