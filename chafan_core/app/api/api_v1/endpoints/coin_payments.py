from typing import Any, List

from fastapi import APIRouter, Depends

from chafan_core.app import crud, models, schemas
from chafan_core.app.api import deps
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.materialize import Materializer

router = APIRouter()


def _payment_schema_from_orm(
    broker: DataBroker,
    *,
    payment: models.CoinPayment,
    receiver_id: int,
) -> schemas.CoinPayment:
    event = None
    m = Materializer(broker, receiver_id)
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
    return schemas.CoinPayment(
        **d,
    )


@router.get("/", response_model=List[schemas.CoinPayment])
def get_payments(
    *,
    broker: DataBroker = Depends(deps.get_data_broker_with_params()),
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    payments = crud.coin_payment.get_multi_by_user(
        broker.get_db(), user_id=current_user_id
    )
    return [
        _payment_schema_from_orm(broker, payment=p, receiver_id=current_user_id)
        for p in payments
    ]
