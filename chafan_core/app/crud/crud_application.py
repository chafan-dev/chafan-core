import datetime
from typing import List, Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.application import Application
from chafan_core.app.schemas.application import ApplicationCreate, ApplicationUpdate


class CRUDApplication(CRUDBase[Application, ApplicationCreate, ApplicationUpdate]):
    def get_pending_applications(
        self, db: Session, *, site_id: int
    ) -> List[Application]:
        return (
            db.query(Application)
            .filter_by(applied_site_id=site_id, pending=True)
            .order_by(Application.created_at.asc())
            .all()
        )

    def create_with_applicant(
        self,
        db: Session,
        *,
        create_in: ApplicationCreate,
        applicant_id: int,
    ) -> Application:
        obj_in_data = jsonable_encoder(create_in)
        db_obj = self.model(
            **obj_in_data,
            applicant_id=applicant_id,
            created_at=datetime.datetime.now(tz=datetime.timezone.utc),
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_applicant_and_site(
        self, db: Session, *, applicant: models.User, site: models.Site
    ) -> Optional[Application]:
        return (
            db.query(Application)
            .filter_by(applicant_id=applicant.id, applied_site_id=site.id)
            .first()
        )


application = CRUDApplication(Application)
