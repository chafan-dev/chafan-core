import datetime

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.form_response import FormResponse
from chafan_core.app.schemas.form_response import FormResponseCreate, FormResponseUpdate


class CRUDFormResponse(CRUDBase[FormResponse, FormResponseCreate, FormResponseUpdate]):
    def create_with_author(
        self,
        db: Session,
        *,
        obj_in: FormResponseCreate,
        response_author_id: int,
        form: models.Form,
    ) -> FormResponse:
        obj_in_data = jsonable_encoder(obj_in)
        del obj_in_data["form_uuid"]
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        db_obj = self.model(
            **obj_in_data,
            response_author_id=response_author_id,
            created_at=utc_now,
            form_id=form.id,
        )
        db.add(db_obj)
        db.commit()
        return db_obj


form_response = CRUDFormResponse(FormResponse)
