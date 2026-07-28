import datetime
from typing import Any, List, Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import coins, models
from chafan_core.app.models.coin_payment import CoinPayment
from chafan_core.app.schemas.coin_payment import CoinPaymentCreate


def get(db: Session, id: Any) -> Optional[CoinPayment]:
    return db.query(CoinPayment).filter(CoinPayment.id == id).first()


def make_payment(
    db: Session,
    *,
    obj_in: CoinPaymentCreate,
    payer: models.User,
    payee: models.User,
) -> CoinPayment:
    coins.deduct_coins(db, payer, obj_in.amount, "coin_payment_out")
    coins.award_coins(db, payee, obj_in.amount, "coin_payment_in")
    payment = CoinPayment(
        **jsonable_encoder(obj_in),
        created_at=datetime.datetime.now(tz=datetime.timezone.utc),
        payer_id=payer.id,
    )
    db.add(payment)
    db.flush()
    db.refresh(payment)
    return payment


def get_with_event_json_and_payee_id(
    db: Session, *, event_json: str, payee_id: int
) -> Optional[CoinPayment]:
    return (
        db.query(CoinPayment)
        .filter_by(event_json=event_json, payee_id=payee_id)
        .first()
    )


def get_multi_by_user(
    db: Session, *, user_id: int, skip: int = 0, limit: int = 50
) -> List[CoinPayment]:
    return (
        db.query(CoinPayment)
        .filter((CoinPayment.payee_id == user_id) | (CoinPayment.payer_id == user_id))
        .order_by(CoinPayment.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
