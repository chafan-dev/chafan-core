import asyncio
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.coin_payment import CoinPaymentCreate
from chafan_core.app.schemas.user import UserCreate
from chafan_core.tests.utils.utils import (
    random_email,
    random_password,
    random_short_lower_string,
)


def _create_test_user(db: Session, initial_coins: int = 100):
    """Helper to create a test user with initial coins."""
    user_in = UserCreate(
        email=random_email(),
        password=random_password(),
        handle=random_short_lower_string(),
    )
    user = asyncio.run(crud.user.create(db, obj_in=user_in))
    # Give user some coins
    crud.user.update(db, db_obj=user, obj_in={"remaining_coins": initial_coins})
    db.refresh(user)
    return user


def test_make_payment(db: Session) -> None:
    """Test making a coin payment between users."""
    payer = _create_test_user(db, initial_coins=100)
    payee = _create_test_user(db, initial_coins=50)

    payer_initial_coins = payer.remaining_coins
    payee_initial_coins = payee.remaining_coins

    payment_in = CoinPaymentCreate(
        payee_id=payee.id,
        amount=20,
        event_json='{"type": "test_payment"}',
        comment="Test payment",
    )

    payment = crud.coin_payment.make_payment(
        db, obj_in=payment_in, payer=payer, payee=payee
    )

    assert payment is not None
    assert payment.amount == 20
    assert payment.payer_id == payer.id
    assert payment.payee_id == payee.id
    assert payment.comment == "Test payment"
    assert payment.created_at is not None

    # Refresh to get updated coin balances
    db.refresh(payer)
    db.refresh(payee)

    # Payer should have 20 fewer coins
    assert payer.remaining_coins == payer_initial_coins - 20
    # Payee should have 20 more coins
    assert payee.remaining_coins == payee_initial_coins + 20


def test_make_payment_transfers_correct_amount(db: Session) -> None:
    """Test that make_payment transfers the correct amount."""
    payer = _create_test_user(db, initial_coins=1000)
    payee = _create_test_user(db, initial_coins=0)

    payment_in = CoinPaymentCreate(
        payee_id=payee.id,
        amount=500,
        event_json='{"type": "large_payment"}',
    )

    crud.coin_payment.make_payment(db, obj_in=payment_in, payer=payer, payee=payee)

    db.refresh(payer)
    db.refresh(payee)

    assert payer.remaining_coins == 500
    assert payee.remaining_coins == 500


def test_get_with_event_json_and_payee_id(db: Session) -> None:
    """Test getting a payment by event_json and payee_id."""
    payer = _create_test_user(db, initial_coins=100)
    payee = _create_test_user(db, initial_coins=0)

    event_json = '{"type": "unique_event", "id": "12345"}'

    payment_in = CoinPaymentCreate(
        payee_id=payee.id,
        amount=10,
        event_json=event_json,
    )

    created_payment = crud.coin_payment.make_payment(
        db, obj_in=payment_in, payer=payer, payee=payee
    )

    retrieved_payment = crud.coin_payment.get_with_event_json_and_payee_id(
        db, event_json=event_json, payee_id=payee.id
    )

    assert retrieved_payment is not None
    assert retrieved_payment.id == created_payment.id


def test_get_with_event_json_and_payee_id_returns_none_when_not_found(
    db: Session,
) -> None:
    """Test that get_with_event_json_and_payee_id returns None when not found."""
    result = crud.coin_payment.get_with_event_json_and_payee_id(
        db, event_json='{"nonexistent": true}', payee_id=99999
    )
    assert result is None


def test_get_multi_by_user_as_payer(db: Session) -> None:
    """Test getting payments where user is the payer."""
    payer = _create_test_user(db, initial_coins=100)
    payee1 = _create_test_user(db, initial_coins=0)
    payee2 = _create_test_user(db, initial_coins=0)

    # Create payments from payer
    for i, payee in enumerate([payee1, payee2]):
        payment_in = CoinPaymentCreate(
            payee_id=payee.id,
            amount=10,
            event_json=f'{{"payment_num": {i}}}',
        )
        crud.coin_payment.make_payment(db, obj_in=payment_in, payer=payer, payee=payee)

    # Get payments for payer
    payments = crud.coin_payment.get_multi_by_user(db, user_id=payer.id)

    # Should include payments where payer is the payer
    payer_ids = [p.payer_id for p in payments]
    assert payer.id in payer_ids


def test_get_multi_by_user_as_payee(db: Session) -> None:
    """Test getting payments where user is the payee."""
    payer1 = _create_test_user(db, initial_coins=100)
    payer2 = _create_test_user(db, initial_coins=100)
    payee = _create_test_user(db, initial_coins=0)

    # Create payments to payee
    for i, payer in enumerate([payer1, payer2]):
        payment_in = CoinPaymentCreate(
            payee_id=payee.id,
            amount=10,
            event_json=f'{{"received_payment_num": {i}}}',
        )
        crud.coin_payment.make_payment(db, obj_in=payment_in, payer=payer, payee=payee)

    # Get payments for payee
    payments = crud.coin_payment.get_multi_by_user(db, user_id=payee.id)

    # Should include payments where payee is the payee
    payee_ids = [p.payee_id for p in payments]
    assert payee.id in payee_ids


def test_get_multi_by_user_pagination(db: Session) -> None:
    """Test pagination of get_multi_by_user."""
    payer = _create_test_user(db, initial_coins=1000)
    payee = _create_test_user(db, initial_coins=0)

    # Create several payments
    for i in range(5):
        payment_in = CoinPaymentCreate(
            payee_id=payee.id,
            amount=10,
            event_json=f'{{"pagination_test": {i}}}',
        )
        crud.coin_payment.make_payment(db, obj_in=payment_in, payer=payer, payee=payee)

    # Test skip and limit
    page1 = crud.coin_payment.get_multi_by_user(db, user_id=payer.id, skip=0, limit=2)
    page2 = crud.coin_payment.get_multi_by_user(db, user_id=payer.id, skip=2, limit=2)

    assert len(page1) <= 2
    assert len(page2) <= 2

    # Pages should have different payments
    if len(page1) > 0 and len(page2) > 0:
        page1_ids = {p.id for p in page1}
        page2_ids = {p.id for p in page2}
        assert page1_ids.isdisjoint(page2_ids)


def test_get_payment_by_id(db: Session) -> None:
    """Test getting a payment by ID."""
    payer = _create_test_user(db, initial_coins=100)
    payee = _create_test_user(db, initial_coins=0)

    payment_in = CoinPaymentCreate(
        payee_id=payee.id,
        amount=10,
        event_json='{"test": "get_by_id"}',
    )

    payment = crud.coin_payment.make_payment(
        db, obj_in=payment_in, payer=payer, payee=payee
    )

    retrieved_payment = crud.coin_payment.get(db, id=payment.id)
    assert retrieved_payment is not None
    assert retrieved_payment.id == payment.id


def test_get_payment_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent payment."""
    result = crud.coin_payment.get(db, id=99999999)
    assert result is None


def test_payment_without_comment(db: Session) -> None:
    """Test creating a payment without a comment."""
    payer = _create_test_user(db, initial_coins=100)
    payee = _create_test_user(db, initial_coins=0)

    payment_in = CoinPaymentCreate(
        payee_id=payee.id,
        amount=10,
        event_json='{"test": "no_comment"}',
        comment=None,
    )

    payment = crud.coin_payment.make_payment(
        db, obj_in=payment_in, payer=payer, payee=payee
    )

    assert payment is not None
    assert payment.comment is None


def test_payment_timestamps(db: Session) -> None:
    """Test that payments have correct timestamps."""
    import datetime

    payer = _create_test_user(db, initial_coins=100)
    payee = _create_test_user(db, initial_coins=0)

    before_create = datetime.datetime.now(tz=datetime.timezone.utc)

    payment_in = CoinPaymentCreate(
        payee_id=payee.id,
        amount=10,
        event_json='{"test": "timestamp"}',
    )

    payment = crud.coin_payment.make_payment(
        db, obj_in=payment_in, payer=payer, payee=payee
    )

    after_create = datetime.datetime.now(tz=datetime.timezone.utc)

    assert payment.created_at is not None
    assert before_create <= payment.created_at <= after_create
