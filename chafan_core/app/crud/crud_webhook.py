import datetime
from typing import Any, Dict, Optional, Union

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm.session import Session

from chafan_core.app.models.webhook import Webhook
from chafan_core.app.schemas.webhook import WebhookCreate, WebhookUpdate


def get(db: Session, id: Any) -> Optional[Webhook]:
    return db.query(Webhook).filter(Webhook.id == id).first()


def create_with_site(
    db: Session, *, obj_in: WebhookCreate, site_id: int
) -> Webhook:
    obj_in_data = jsonable_encoder(obj_in)
    del obj_in_data["site_uuid"]
    obj_in_data["site_id"] = site_id
    obj_in_data["updated_at"] = datetime.datetime.now(tz=datetime.timezone.utc)
    db_obj = Webhook(**obj_in_data)
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    return db_obj


def update(
    db: Session, *, db_obj: Webhook, obj_in: Union[WebhookUpdate, Dict[str, Any]]
) -> Webhook:
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_unset=True)
    for field in update_data:
        if hasattr(db_obj, field):
            setattr(db_obj, field, update_data[field])
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    return db_obj
