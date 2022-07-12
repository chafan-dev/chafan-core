import datetime
from typing import Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.coin_deposit import CoinDeposit
from chafan_core.app.schemas.coin_deposit import CoinDepositCreate, CoinDepositUpdate


class CRUDCoinDeposit(CRUDBase[CoinDeposit, CoinDepositCreate, CoinDepositUpdate]):
    def make_deposit(
        self,
        db: Session,
        *,
        obj_in: CoinDepositCreate,
        authorizer_id: int,
        payee: models.User
    ) -> CoinDeposit:
        payee.remaining_coins += obj_in.amount
        deposit = CoinDeposit(
            **jsonable_encoder(obj_in),
            created_at=datetime.datetime.now(tz=datetime.timezone.utc),
            authorizer_id=authorizer_id,
        )
        db.add(deposit)
        db.commit()
        db.refresh(deposit)
        return deposit

    def get_with_ref_id(self, db: Session, *, ref_id: str) -> Optional[CoinDeposit]:
        return db.query(CoinDeposit).filter_by(ref_id=ref_id).first()


coin_deposit = CRUDCoinDeposit(CoinDeposit)
