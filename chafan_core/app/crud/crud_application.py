import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.models.application import Application
from chafan_core.app.schemas.application import ApplicationCreate, ApplicationUpdate


def get(db: Session, id: Any) -> Optional[Application]:
    return db.query(Application).filter(Application.id == id).first()


def get_pending_applications(db: Session, *, site_id: int) -> List[Application]:
    return (
        db.query(Application)
        .filter_by(applied_site_id=site_id, pending=True)
        .order_by(Application.created_at.asc())
        .all()
    )


def create_with_applicant(
    db: Session,
    *,
    create_in: ApplicationCreate,
    applicant_id: int,
) -> Application:
    obj_in_data = jsonable_encoder(create_in)
    db_obj = Application(
        **obj_in_data,
        applicant_id=applicant_id,
        created_at=datetime.datetime.now(tz=datetime.timezone.utc),
    )
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    return db_obj


def get_by_applicant_and_site(
    db: Session, *, applicant: models.User, site: models.Site
) -> Optional[Application]:
    return (
        db.query(Application)
        .filter_by(applicant_id=applicant.id, applied_site_id=site.id)
        .first()
    )


def update(
    db: Session,
    *,
    db_obj: Application,
    obj_in: Union[ApplicationUpdate, Dict[str, Any]],
) -> Application:
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
