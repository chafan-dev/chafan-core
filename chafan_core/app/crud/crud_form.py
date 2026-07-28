import datetime
from typing import Any, Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.models.form import Form
from chafan_core.app.schemas.form import FormCreate
from chafan_core.utils.base import get_uuid


def get(db: Session, id: Any) -> Optional[Form]:
    return db.query(Form).filter(Form.id == id).first()


def get_by_uuid(db: Session, *, uuid: str) -> Optional[Form]:
    return db.query(Form).filter_by(uuid=uuid).first()


def _get_unique_uuid(db: Session) -> str:
    while True:
        uuid = get_uuid()
        if get_by_uuid(db, uuid=uuid) is None:
            return uuid


def create_with_author(
    db: Session,
    *,
    obj_in: FormCreate,
    author: models.User,
) -> Form:
    obj_in_data = jsonable_encoder(obj_in)
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    db_obj = Form(
        **obj_in_data,
        uuid=_get_unique_uuid(db),
        author_id=author.id,
        updated_at=utc_now,
        created_at=utc_now,
    )
    db.add(db_obj)
    db.flush()
    return db_obj
