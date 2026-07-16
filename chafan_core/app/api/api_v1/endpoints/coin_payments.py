from typing import Any, List

from fastapi import APIRouter, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.services import coin_payments as coin_payments_service

router = APIRouter()


@router.get("/", response_model=List[schemas.CoinPayment])
def get_payments(
    *,
    broker: DataBroker = Depends(deps.get_data_broker_with_params()),
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    return coin_payments_service.list_payments(broker, user_id=current_user_id)
