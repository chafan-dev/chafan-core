import datetime
from typing import Any, Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.models.form_response import FormResponse
from chafan_core.app.schemas.form_response import FormResponseCreate


def get(db: Session, id: Any) -> Optional[FormResponse]:
    return db.query(FormResponse).filter(FormResponse.id == id).first()


def create_with_author(
    db: Session,
    *,
    obj_in: FormResponseCreate,
    response_author_id: int,
    form: models.Form,
) -> FormResponse:
    obj_in_data = jsonable_encoder(obj_in)
    del obj_in_data["form_uuid"]
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    db_obj = FormResponse(
        **obj_in_data,
        response_author_id=response_author_id,
        created_at=utc_now,
        form_id=form.id,
    )
    db.add(db_obj)
    db.flush()
    return db_obj
