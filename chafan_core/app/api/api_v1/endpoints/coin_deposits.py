from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.services import coin_deposits as coin_deposits_service

router = APIRouter()


@router.get("/{id}", response_model=schemas.CoinDeposit, include_in_schema=False)
def get_deposit(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    return coin_deposits_service.get_deposit(
        db, deposit_id=id, current_user_id=current_user_id
    )
