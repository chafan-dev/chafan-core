import datetime
from typing import List, Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.coin_payment import CoinPayment
from chafan_core.app.schemas.coin_payment import CoinPaymentCreate, CoinPaymentUpdate


class CRUDCoinPayment(CRUDBase[CoinPayment, CoinPaymentCreate, CoinPaymentUpdate]):
    def make_payment(
        self,
        db: Session,
        *,
        obj_in: CoinPaymentCreate,
        payer: models.User,
        payee: models.User
    ) -> CoinPayment:
        payer.remaining_coins -= obj_in.amount
        payee.remaining_coins += obj_in.amount
        payment = CoinPayment(
            **jsonable_encoder(obj_in),
            created_at=datetime.datetime.now(tz=datetime.timezone.utc),
            payer_id=payer.id,
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        return payment

    def get_with_event_json_and_payee_id(
        self, db: Session, *, event_json: str, payee_id: int
    ) -> Optional[CoinPayment]:
        return (
            db.query(CoinPayment)
            .filter_by(event_json=event_json, payee_id=payee_id)
            .first()
        )

    def get_multi_by_user(
        self, db: Session, *, user_id: int, skip: int = 0, limit: int = 50
    ) -> List[CoinPayment]:
        return (
            db.query(self.model)
            .filter(
                (CoinPayment.payee_id == user_id) | (CoinPayment.payer_id == user_id)
            )
            .order_by(CoinPayment.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )


coin_payment = CRUDCoinPayment(CoinPayment)
