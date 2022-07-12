from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.answer_suggest_edit import AnswerSuggestEdit
from chafan_core.app.schemas.answer_suggest_edit import (
    AnswerSuggestEditCreate,
    AnswerSuggestEditUpdate,
)
from chafan_core.utils.base import get_utc_now


class CRUDAnswerSuggestEdit(
    CRUDBase[AnswerSuggestEdit, AnswerSuggestEditCreate, AnswerSuggestEditUpdate]
):
    def create_with_author(
        self,
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
        db_obj = self.model(
            **obj_in_data,
            uuid=self.get_unique_uuid(db),
            answer_id=answer.id,
            author_id=author_id,
            status="pending",
            created_at=get_utc_now(),
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


answer_suggest_edit = CRUDAnswerSuggestEdit(AnswerSuggestEdit)
