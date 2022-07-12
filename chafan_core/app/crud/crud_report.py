import datetime
from typing import Callable, List

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.utils.base import unwrap
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.report import Report
from chafan_core.app.schemas.report import ReportCreate, ReportUpdate


class CRUDReport(CRUDBase[Report, ReportCreate, ReportUpdate]):
    def create_with_author(
        self,
        db: Session,
        *,
        obj_in: ReportCreate,
        author_id: int,
        check_site: Callable[[models.Site], None]
    ) -> Report:
        obj_in_data = jsonable_encoder(obj_in)
        if "question_uuid" in obj_in_data:
            if obj_in_data["question_uuid"]:
                question = unwrap(
                    crud.question.get_by_uuid(db, uuid=obj_in_data["question_uuid"])
                )
                check_site(question.site)
                obj_in_data["question_id"] = question.id
            del obj_in_data["question_uuid"]
        if "submission_uuid" in obj_in_data:
            if obj_in_data["submission_uuid"]:
                submission = unwrap(
                    crud.submission.get_by_uuid(db, uuid=obj_in_data["submission_uuid"])
                )
                check_site(submission.site)
                obj_in_data["submission_id"] = submission.id
            del obj_in_data["submission_uuid"]
        if "answer_uuid" in obj_in_data:
            if obj_in_data["answer_uuid"]:
                answer = unwrap(
                    crud.answer.get_by_uuid(db, uuid=obj_in_data["answer_uuid"])
                )
                check_site(answer.site)
                obj_in_data["answer_id"] = answer.id
            del obj_in_data["answer_uuid"]
        if "comment_uuid" in obj_in_data:
            if obj_in_data["comment_uuid"]:
                comment = unwrap(
                    crud.comment.get_by_uuid(db, uuid=obj_in_data["comment_uuid"])
                )
                if comment.site:
                    check_site(comment.site)
                obj_in_data["comment_id"] = comment.id
            del obj_in_data["comment_uuid"]
        if "article_uuid" in obj_in_data:
            if obj_in_data["article_uuid"]:
                obj_in_data["article_id"] = crud.article.get_by_uuid(db, uuid=obj_in_data["article_uuid"]).id  # type: ignore
            del obj_in_data["article_uuid"]
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        db_obj = self.model(**obj_in_data, author_id=author_id, created_at=utc_now,)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_all(self, db: Session) -> List[Report]:
        return db.query(Report).all()


report = CRUDReport(Report)
