import datetime

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm.session import Session

from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.webhook import Webhook
from chafan_core.app.schemas.webhook import WebhookCreate, WebhookUpdate


class CRUDWebhook(CRUDBase[Webhook, WebhookCreate, WebhookUpdate]):
    def create_with_site(
        self, db: Session, *, obj_in: WebhookCreate, site_id: int
    ) -> Webhook:
        obj_in_data = jsonable_encoder(obj_in)
        del obj_in_data["site_uuid"]
        obj_in_data["site_id"] = site_id
        obj_in_data["updated_at"] = datetime.datetime.now(tz=datetime.timezone.utc)
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


webhook = CRUDWebhook(Webhook)
