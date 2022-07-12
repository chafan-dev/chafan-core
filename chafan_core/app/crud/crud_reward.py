import datetime

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models import Reward
from chafan_core.app.schemas import RewardCreate, RewardUpdate


class CRUDReward(CRUDBase[Reward, RewardCreate, RewardUpdate]):
    def create_with_giver(
        self,
        db: Session,
        *,
        obj_in: RewardCreate,
        giver: models.User,
    ) -> Reward:
        giver.remaining_coins -= obj_in.coin_amount
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        obj_in_data = jsonable_encoder(obj_in)
        obj_in_data["expired_at"] = utc_now + datetime.timedelta(
            days=obj_in_data["expired_after_days"]
        )
        del obj_in_data["expired_after_days"]
        receiver = crud.user.get_by_uuid(db, uuid=obj_in_data["receiver_uuid"])
        del obj_in_data["receiver_uuid"]
        assert receiver is not None
        db_obj = self.model(
            **obj_in_data,
            giver_id=giver.id,
            created_at=utc_now,
            receiver_id=receiver.id,
        )
        db.add(db_obj)
        db.add(giver)
        db.commit()
        return db_obj


reward = CRUDReward(Reward)
