from typing import Any, List

from fastapi import APIRouter, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import coin_payments as coin_payments_service

router = APIRouter()


@router.get("/", response_model=List[schemas.CoinPayment])
def get_payments(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    return coin_payments_service.list_payments(
        ctx, user_id=ctx.unwrapped_principal_id()
    )
