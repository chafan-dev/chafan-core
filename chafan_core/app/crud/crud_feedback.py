from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session

from chafan_core.app.models.feedback import Feedback
from chafan_core.app.schemas.feedback import FeedbackUpdate


def get(db: Session, id: Any) -> Optional[Feedback]:
    return db.query(Feedback).filter(Feedback.id == id).first()


def get_multi(db: Session, *, skip: int = 0, limit: int = 100) -> List[Feedback]:
    return db.query(Feedback).offset(skip).limit(limit).all()


def update(
    db: Session, *, db_obj: Feedback, obj_in: Union[FeedbackUpdate, Dict[str, Any]]
) -> Feedback:
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
