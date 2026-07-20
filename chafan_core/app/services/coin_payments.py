"""Coin payment listing service."""

from __future__ import annotations

from typing import List

from chafan_core.app import crud, models, schemas
from chafan_core.app.data_broker import DataBroker


def payment_schema_from_orm(
    broker: DataBroker,
    *,
    payment: models.CoinPayment,
    receiver_id: int,
) -> schemas.CoinPayment:
    event = None
    m = broker.as_principal(receiver_id)
    if payment.event_json:
        event = m.materialize_event(payment.event_json)
    base = schemas.CoinPaymentInDBBase.from_orm(payment)
    payer = crud.user.get(broker.get_db(), id=payment.payer_id)
    assert payer is not None
    payee = crud.user.get(broker.get_db(), id=payment.payee_id)
    assert payee is not None
    d = base.dict()
    d["payer"] = m.preview_of_user(payer)
    d["payee"] = m.preview_of_user(payee)
    d["event"] = event
    return schemas.CoinPayment(**d)


def list_payments(broker: DataBroker, *, user_id: int) -> List[schemas.CoinPayment]:
    payments = crud.coin_payment.get_multi_by_user(broker.get_db(), user_id=user_id)
    return [
        payment_schema_from_orm(broker, payment=p, receiver_id=user_id)
        for p in payments
    ]
