import datetime
from typing import Any, Dict, List, Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.common import is_dev
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.crud.crud_activity import upvote_answer_activity
from chafan_core.app.models.answer import Answer, Answer_Upvotes
from chafan_core.app.models.user import User
from chafan_core.app.schemas.answer import AnswerCreate, AnswerUpdate
from chafan_core.app.search import es_search


class CRUDAnswer(CRUDBase[Answer, AnswerCreate, AnswerUpdate]):
    def get_one_as_search_result(self, db: Session, id: int) -> Optional[Answer]:
        answer = db.query(self.model).filter_by(id=id).first()
        if not answer or answer.is_hidden_by_moderator:
            return None
        if not answer.is_published:
            return None
        return answer

    def create_with_author(
        self, db: Session, *, obj_in: AnswerCreate, author_id: int, site_id: int
    ) -> Answer:
        obj_in_data = jsonable_encoder(obj_in)
        question = crud.question.get_by_uuid(db, uuid=obj_in_data["question_uuid"])
        assert question is not None
        obj_in_data["question_id"] = question.id
        del obj_in_data["question_uuid"]
        del obj_in_data["writing_session_uuid"]
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)

        del obj_in_data["content"]
        obj_in_data["body"] = obj_in.content.source
        obj_in_data["body_prerendered_text"] = obj_in.content.rendered_text
        obj_in_data["editor"] = obj_in.content.editor

        db_obj = self.model(
            **obj_in_data,
            author_id=author_id,
            site_id=site_id,
            updated_at=utc_now,
            uuid=self.get_unique_uuid(db),
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        db.commit()
        return db_obj

    def upvote(self, db: Session, *, db_obj: Answer, voter: User) -> Answer:
        answer_upvote = (
            db.query(Answer_Upvotes)
            .filter_by(answer_id=db_obj.id, voter_id=voter.id)
            .first()
        )
        if answer_upvote is None:
            answer_upvote = Answer_Upvotes(answer=db_obj, voter=voter)
            db.add(answer_upvote)
            db_obj.upvotes_count += 1
            db.commit()
            db.refresh(db_obj)
            db.add(
                upvote_answer_activity(
                    voter=voter,
                    site_id=db_obj.site_id,
                    answer=db_obj,
                    created_at=datetime.datetime.now(tz=datetime.timezone.utc),
                )
            )
            db.commit()
        elif answer_upvote.cancelled:
            db_obj.upvotes_count += 1
            answer_upvote.cancelled = False
            db.commit()
        return db_obj

    def cancel_upvote(self, db: Session, *, db_obj: Answer, voter: User) -> Answer:
        answer_upvote = (
            db.query(Answer_Upvotes)
            .filter_by(answer_id=db_obj.id, voter_id=voter.id)
            .first()
        )
        if answer_upvote is not None and not answer_upvote.cancelled:
            db_obj.upvotes_count -= 1
            assert db_obj.upvotes_count >= 0
            answer_upvote.cancelled = True
            db.commit()
            db.refresh(db_obj)
        return db_obj

    def search(self, db: Session, *, q: str) -> List[Answer]:
        if is_dev():
            return self.get_all_published(db)
        ids = es_search("answer", query=q)
        if not ids:
            return []
        ret = []
        for id in ids:
            answer = self.get_one_as_search_result(db, id=id)
            if answer:
                ret.append(answer)
        return ret

    def update_checked(
        self, db: Session, *, db_obj: Answer, obj_in: Dict[str, Any]
    ) -> Answer:
        if db_obj.is_published and "is_published" in obj_in:
            assert obj_in["is_published"]
        return self.update(db, db_obj=db_obj, obj_in=obj_in)

    def delete_forever(self, db: Session, *, answer: Answer) -> None:
        answer.is_deleted = True
        answer.body = "[DELETED]"
        answer.body_draft = "[DELETED]"
        answer.body_prerendered_text = "[DELETED]"
        for archive in answer.archives:
            archive.body = "[DELETED]"
        db.add(answer)
        db.commit()

    def get_all_published(self, db: Session) -> List[Answer]:
        return db.query(Answer).filter_by(is_deleted=False, is_published=True).all()

    def get_all(self, db: Session) -> List[Answer]:
        return db.query(Answer).all()


answer = CRUDAnswer(Answer)
