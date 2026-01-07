import asyncio
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.coin_deposit import CoinDepositCreate
from chafan_core.app.schemas.user import UserCreate
from chafan_core.utils.base import get_uuid
from chafan_core.tests.utils.utils import (
    random_email,
    random_password,
    random_short_lower_string,
)


def _create_test_user(db: Session, initial_coins: int = 0):
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


def test_make_deposit(db: Session) -> None:
    """Test making a coin deposit to a user."""
    authorizer = _create_test_user(db)
    payee = _create_test_user(db, initial_coins=50)

    payee_initial_coins = payee.remaining_coins

    deposit_in = CoinDepositCreate(
        payee_id=payee.id,
        amount=100,
        ref_id=f"test_deposit_{get_uuid()}",
        comment="Test deposit",
    )

    deposit = crud.coin_deposit.make_deposit(
        db, obj_in=deposit_in, authorizer_id=authorizer.id, payee=payee
    )

    assert deposit is not None
    assert deposit.amount == 100
    assert deposit.payee_id == payee.id
    assert deposit.authorizer_id == authorizer.id
    assert deposit.comment == "Test deposit"
    assert deposit.created_at is not None

    # Refresh to get updated coin balance
    db.refresh(payee)

    # Payee should have 100 more coins
    assert payee.remaining_coins == payee_initial_coins + 100


def test_make_deposit_increases_coins(db: Session) -> None:
    """Test that make_deposit correctly increases user's coins."""
    authorizer = _create_test_user(db)
    payee = _create_test_user(db, initial_coins=0)

    deposit_in = CoinDepositCreate(
        payee_id=payee.id,
        amount=500,
        ref_id=f"large_deposit_{get_uuid()}",
        comment="Large deposit",
    )

    crud.coin_deposit.make_deposit(
        db, obj_in=deposit_in, authorizer_id=authorizer.id, payee=payee
    )

    db.refresh(payee)
    assert payee.remaining_coins == 500


def test_get_with_ref_id(db: Session) -> None:
    """Test getting a deposit by ref_id."""
    authorizer = _create_test_user(db)
    payee = _create_test_user(db)

    ref_id = f"unique_ref_{get_uuid()}"

    deposit_in = CoinDepositCreate(
        payee_id=payee.id,
        amount=100,
        ref_id=ref_id,
        comment="Deposit with unique ref_id",
    )

    created_deposit = crud.coin_deposit.make_deposit(
        db, obj_in=deposit_in, authorizer_id=authorizer.id, payee=payee
    )

    retrieved_deposit = crud.coin_deposit.get_with_ref_id(db, ref_id=ref_id)

    assert retrieved_deposit is not None
    assert retrieved_deposit.id == created_deposit.id
    assert retrieved_deposit.ref_id == ref_id


def test_get_with_ref_id_returns_none_when_not_found(db: Session) -> None:
    """Test that get_with_ref_id returns None when not found."""
    result = crud.coin_deposit.get_with_ref_id(db, ref_id="nonexistent_ref_id")
    assert result is None


def test_get_deposit_by_id(db: Session) -> None:
    """Test getting a deposit by ID."""
    authorizer = _create_test_user(db)
    payee = _create_test_user(db)

    deposit_in = CoinDepositCreate(
        payee_id=payee.id,
        amount=100,
        ref_id=f"get_by_id_test_{get_uuid()}",
        comment="Test get by ID",
    )

    deposit = crud.coin_deposit.make_deposit(
        db, obj_in=deposit_in, authorizer_id=authorizer.id, payee=payee
    )

    retrieved_deposit = crud.coin_deposit.get(db, id=deposit.id)
    assert retrieved_deposit is not None
    assert retrieved_deposit.id == deposit.id


def test_get_deposit_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent deposit."""
    result = crud.coin_deposit.get(db, id=99999999)
    assert result is None


def test_deposit_without_comment(db: Session) -> None:
    """Test creating a deposit without a comment."""
    authorizer = _create_test_user(db)
    payee = _create_test_user(db)

    deposit_in = CoinDepositCreate(
        payee_id=payee.id,
        amount=100,
        ref_id=f"no_comment_{get_uuid()}",
        comment=None,
    )

    deposit = crud.coin_deposit.make_deposit(
        db, obj_in=deposit_in, authorizer_id=authorizer.id, payee=payee
    )

    assert deposit is not None
    assert deposit.comment is None


def test_deposit_timestamps(db: Session) -> None:
    """Test that deposits have correct timestamps."""
    import datetime

    authorizer = _create_test_user(db)
    payee = _create_test_user(db)

    before_create = datetime.datetime.now(tz=datetime.timezone.utc)

    deposit_in = CoinDepositCreate(
        payee_id=payee.id,
        amount=100,
        ref_id=f"timestamp_test_{get_uuid()}",
        comment="Timestamp test",
    )

    deposit = crud.coin_deposit.make_deposit(
        db, obj_in=deposit_in, authorizer_id=authorizer.id, payee=payee
    )

    after_create = datetime.datetime.now(tz=datetime.timezone.utc)

    assert deposit.created_at is not None
    assert before_create <= deposit.created_at <= after_create


def test_multiple_deposits_to_same_user(db: Session) -> None:
    """Test making multiple deposits to the same user."""
    authorizer = _create_test_user(db)
    payee = _create_test_user(db, initial_coins=0)

    # Make multiple deposits
    for i in range(3):
        deposit_in = CoinDepositCreate(
            payee_id=payee.id,
            amount=100,
            ref_id=f"multi_deposit_{i}_{get_uuid()}",
            comment=f"Deposit {i}",
        )
        crud.coin_deposit.make_deposit(
            db, obj_in=deposit_in, authorizer_id=authorizer.id, payee=payee
        )

    db.refresh(payee)
    # Should have 300 coins total
    assert payee.remaining_coins == 300


def test_deposits_with_unique_ref_ids(db: Session) -> None:
    """Test that each deposit has a unique ref_id."""
    authorizer = _create_test_user(db)
    payee = _create_test_user(db)

    ref_id1 = f"ref_1_{get_uuid()}"
    ref_id2 = f"ref_2_{get_uuid()}"

    deposit1_in = CoinDepositCreate(
        payee_id=payee.id,
        amount=100,
        ref_id=ref_id1,
        comment="First deposit",
    )

    deposit2_in = CoinDepositCreate(
        payee_id=payee.id,
        amount=100,
        ref_id=ref_id2,
        comment="Second deposit",
    )

    deposit1 = crud.coin_deposit.make_deposit(
        db, obj_in=deposit1_in, authorizer_id=authorizer.id, payee=payee
    )

    deposit2 = crud.coin_deposit.make_deposit(
        db, obj_in=deposit2_in, authorizer_id=authorizer.id, payee=payee
    )

    assert deposit1.ref_id != deposit2.ref_id
    assert deposit1.id != deposit2.id


def test_different_authorizers_can_make_deposits(db: Session) -> None:
    """Test that different authorizers can make deposits to the same user."""
    authorizer1 = _create_test_user(db)
    authorizer2 = _create_test_user(db)
    payee = _create_test_user(db, initial_coins=0)

    deposit1_in = CoinDepositCreate(
        payee_id=payee.id,
        amount=50,
        ref_id=f"auth1_deposit_{get_uuid()}",
        comment="From authorizer 1",
    )

    deposit2_in = CoinDepositCreate(
        payee_id=payee.id,
        amount=75,
        ref_id=f"auth2_deposit_{get_uuid()}",
        comment="From authorizer 2",
    )

    deposit1 = crud.coin_deposit.make_deposit(
        db, obj_in=deposit1_in, authorizer_id=authorizer1.id, payee=payee
    )

    deposit2 = crud.coin_deposit.make_deposit(
        db, obj_in=deposit2_in, authorizer_id=authorizer2.id, payee=payee
    )

    assert deposit1.authorizer_id == authorizer1.id
    assert deposit2.authorizer_id == authorizer2.id

    db.refresh(payee)
    assert payee.remaining_coins == 125
