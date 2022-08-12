import datetime
from typing import List, Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.common import is_dev
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.crud.crud_activity import upvote_question_activity
from chafan_core.app.models.question import Question, QuestionUpvotes
from chafan_core.app.models.topic import Topic
from chafan_core.app.schemas.question import QuestionCreate, QuestionUpdate
from chafan_core.app.search import do_search


class CRUDQuestion(CRUDBase[Question, QuestionCreate, QuestionUpdate]):
    def get_by_id(self, db: Session, *, id: int) -> Optional[Question]:
        return db.query(Question).filter(Question.id == id).first()

    def create_with_author(
        self, db: Session, *, obj_in: QuestionCreate, author_id: int
    ) -> Question:
        site = crud.site.get_by_uuid(db, uuid=obj_in.site_uuid)
        assert site is not None
        obj_in_data = jsonable_encoder(obj_in)
        del obj_in_data["site_uuid"]
        obj_in_data["site_id"] = site.id
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        db_obj = self.model(
            **obj_in_data,
            uuid=self.get_unique_uuid(db),
            author_id=author_id,
            editor_id=author_id,
            updated_at=utc_now,
            created_at=utc_now,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_topics(
        self, db: Session, *, db_obj: Question, new_topics: List[Topic]
    ) -> Question:
        db_obj.topics.clear()
        db_obj.topics = new_topics
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def search(self, db: Session, *, q: str) -> List[Question]:
        if is_dev():
            return self.get_all_valid(db)
        ids = do_search("question", query=q)
        if not ids:
            return []
        ret = []
        for id in ids:
            question = self.get(db, id=id)
            if question:
                ret.append(question)
        return ret

    def get_placed_at_home(self, db: Session) -> List[Question]:
        return db.query(Question).filter_by(is_placed_at_home=True).all()

    def upvote(self, db: Session, *, db_obj: Question, voter: models.User) -> Question:
        question_upvote = (
            db.query(QuestionUpvotes)
            .filter_by(question_id=db_obj.id, voter_id=voter.id)
            .first()
        )
        if question_upvote is None:
            question_upvote = QuestionUpvotes(question=db_obj, voter=voter)
            db.add(question_upvote)
            db_obj.upvotes_count += 1
            db.commit()
            db.refresh(db_obj)
            db.add(
                upvote_question_activity(
                    voter=voter,
                    site_id=db_obj.site_id,
                    question=db_obj,
                    created_at=datetime.datetime.now(tz=datetime.timezone.utc),
                )
            )
            db.commit()
        elif question_upvote.cancelled:
            db_obj.upvotes_count += 1
            question_upvote.cancelled = False
            db.commit()
        return db_obj

    def cancel_upvote(
        self, db: Session, *, db_obj: Question, voter: models.User
    ) -> Question:
        question_upvote = (
            db.query(QuestionUpvotes)
            .filter_by(question_id=db_obj.id, voter_id=voter.id)
            .first()
        )
        if question_upvote is not None and not question_upvote.cancelled:
            db_obj.upvotes_count -= 1
            assert db_obj.upvotes_count >= 0
            question_upvote.cancelled = True
            db.commit()
            db.refresh(db_obj)
        return db_obj

    def get_all_valid(self, db: Session) -> List[Question]:
        return db.query(Question).filter_by(is_hidden=False).all()


question = CRUDQuestion(Question)
