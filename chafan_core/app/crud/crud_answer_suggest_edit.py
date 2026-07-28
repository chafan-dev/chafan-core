from typing import Any, Dict, Optional, Union

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.models.answer_suggest_edit import AnswerSuggestEdit
from chafan_core.app.schemas.answer_suggest_edit import (
    AnswerSuggestEditCreate,
    AnswerSuggestEditUpdate,
)
from chafan_core.utils.base import get_utc_now, get_uuid


def get(db: Session, id: Any) -> Optional[AnswerSuggestEdit]:
    return db.query(AnswerSuggestEdit).filter(AnswerSuggestEdit.id == id).first()


def get_by_uuid(db: Session, *, uuid: str) -> Optional[AnswerSuggestEdit]:
    return db.query(AnswerSuggestEdit).filter_by(uuid=uuid).first()


def _get_unique_uuid(db: Session) -> str:
    while True:
        uuid = get_uuid()
        if get_by_uuid(db, uuid=uuid) is None:
            return uuid


def create_with_author(
    db: Session,
    *,
    obj_in: AnswerSuggestEditCreate,
    author_id: int,
    answer: models.Answer,
) -> AnswerSuggestEdit:
    obj_in_data = jsonable_encoder(obj_in)
    del obj_in_data["body_rich_text"]
    if obj_in.body_rich_text:
        obj_in_data["body"] = obj_in.body_rich_text.source
        obj_in_data["body_editor"] = obj_in.body_rich_text.editor
        obj_in_data["body_text"] = obj_in.body_rich_text.rendered_text
    del obj_in_data["answer_uuid"]
    db_obj = AnswerSuggestEdit(
        **obj_in_data,
        uuid=_get_unique_uuid(db),
        answer_id=answer.id,
        author_id=author_id,
        status="pending",
        created_at=get_utc_now(),
    )
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    return db_obj


def update(
    db: Session,
    *,
    db_obj: AnswerSuggestEdit,
    obj_in: Union[AnswerSuggestEditUpdate, Dict[str, Any]],
) -> AnswerSuggestEdit:
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
