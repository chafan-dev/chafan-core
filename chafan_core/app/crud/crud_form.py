import datetime

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.form import Form
from chafan_core.app.schemas.form import FormCreate, FormUpdate


class CRUDForm(CRUDBase[Form, FormCreate, FormUpdate]):
    def create_with_author(
        self,
        db: Session,
        *,
        obj_in: FormCreate,
        author: models.User,
    ) -> Form:
        obj_in_data = jsonable_encoder(obj_in)
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        db_obj = self.model(
            **obj_in_data,
            uuid=self.get_unique_uuid(db),
            author_id=author.id,
            updated_at=utc_now,
            created_at=utc_now,
        )
        db.add(db_obj)
        db.commit()
        return db_obj


form = CRUDForm(Form)
