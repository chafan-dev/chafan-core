from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.utils.base import HTTPException_

router = APIRouter()


@router.get("/{id}", response_model=schemas.CoinDeposit, include_in_schema=False)
def get_deposit(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    deposit = crud.coin_deposit.get(db, id=id)
    if deposit is None:
        raise HTTPException_(
            status_code=400,
            detail="The deposit doesn't exist in the system.",
        )
    if current_user_id not in (deposit.authorizer_id, deposit.payee_id):
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    return deposit
