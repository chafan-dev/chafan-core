"""Coin deposit domain service."""

from __future__ import annotations

from chafan_core.app import crud, schemas
from chafan_core.utils.base import HTTPException_


def get_deposit(db, *, deposit_id: int, current_user_id: int) -> schemas.CoinDeposit:
    deposit = crud.coin_deposit.get(db, id=deposit_id)
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
