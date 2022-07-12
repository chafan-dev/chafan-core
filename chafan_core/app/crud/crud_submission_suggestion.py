import datetime

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.submission_suggestion import SubmissionSuggestion
from chafan_core.app.schemas.submission_suggestion import (
    SubmissionSuggestionCreate,
    SubmissionSuggestionUpdate,
)


class CRUDSubmissionSuggestion(
    CRUDBase[
        SubmissionSuggestion, SubmissionSuggestionCreate, SubmissionSuggestionUpdate
    ]
):
    def create_with_author(
        self,
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
        db_obj = self.model(
            **obj_in_data,
            uuid=self.get_unique_uuid(db),
            submission_id=submission.id,
            author_id=author_id,
            status="pending",
            created_at=utc_now,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


submission_suggestion = CRUDSubmissionSuggestion(SubmissionSuggestion)
