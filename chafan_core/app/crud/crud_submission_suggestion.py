import datetime
from typing import Any, Dict, Optional, Union

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.models.submission_suggestion import SubmissionSuggestion
from chafan_core.app.schemas.submission_suggestion import (
    SubmissionSuggestionCreate,
    SubmissionSuggestionUpdate,
)
from chafan_core.utils.base import get_uuid


def get(db: Session, id: Any) -> Optional[SubmissionSuggestion]:
    return db.query(SubmissionSuggestion).filter(SubmissionSuggestion.id == id).first()


def get_by_uuid(db: Session, *, uuid: str) -> Optional[SubmissionSuggestion]:
    return db.query(SubmissionSuggestion).filter_by(uuid=uuid).first()


def _get_unique_uuid(db: Session) -> str:
    while True:
        uuid = get_uuid()
        if get_by_uuid(db, uuid=uuid) is None:
            return uuid


def create_with_author(
    db: Session,
    *,
    obj_in: SubmissionSuggestionCreate,
    author_id: int,
    submission: models.Submission,
) -> SubmissionSuggestion:
    obj_in_data = jsonable_encoder(obj_in)
    del obj_in_data["desc"]
    if obj_in.desc:
        obj_in_data["description"] = obj_in.desc.source
        obj_in_data["description_editor"] = obj_in.desc.editor
        obj_in_data["description_text"] = obj_in.desc.rendered_text
    del obj_in_data["submission_uuid"]
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    db_obj = SubmissionSuggestion(
        **obj_in_data,
        uuid=_get_unique_uuid(db),
        submission_id=submission.id,
        author_id=author_id,
        status="pending",
        created_at=utc_now,
    )
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    return db_obj


def update(
    db: Session,
    *,
    db_obj: SubmissionSuggestion,
    obj_in: Union[SubmissionSuggestionUpdate, Dict[str, Any]],
) -> SubmissionSuggestion:
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
