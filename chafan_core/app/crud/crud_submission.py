import datetime
from typing import List

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.crud.crud_activity import (
    create_submission_activity,
    upvote_submission_activity,
)
from chafan_core.app.models.submission import Submission, SubmissionUpvotes
from chafan_core.app.models.topic import Topic
from chafan_core.app.schemas.submission import SubmissionCreate, SubmissionUpdate
from chafan_core.app.search import es_search


class CRUDSubmission(CRUDBase[Submission, SubmissionCreate, SubmissionUpdate]):
    def create_with_author(
        self, db: Session, *, obj_in: SubmissionCreate, author_id: int
    ) -> Submission:
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
            updated_at=utc_now,
            created_at=utc_now,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        db.add(
            create_submission_activity(
                submission=db_obj, site=db_obj.site, created_at=utc_now,
            )
        )
        db.commit()
        return db_obj

    def update_topics(
        self, db: Session, *, db_obj: Submission, new_topics: List[Topic]
    ) -> Submission:
        db_obj.topics.clear()
        db_obj.topics = new_topics
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def search(self, db: Session, *, q: str) -> List[Submission]:
        ids = es_search("submission", query=q)
        if not ids:
            return []
        ret = []
        for id in ids:
            submission = self.get(db, id=id)
            if submission:
                ret.append(submission)
        return ret

    def upvote(
        self, db: Session, *, db_obj: Submission, voter: models.User
    ) -> Submission:
        submission_upvote = (
            db.query(SubmissionUpvotes)
            .filter_by(submission_id=db_obj.id, voter_id=voter.id)
            .first()
        )
        if submission_upvote is None:
            submission_upvote = SubmissionUpvotes(submission=db_obj, voter=voter)
            db.add(submission_upvote)
            db_obj.upvotes_count += 1
            db.commit()
            db.refresh(db_obj)
            db.add(
                upvote_submission_activity(
                    voter=voter,
                    site_id=db_obj.site_id,
                    submission=db_obj,
                    created_at=datetime.datetime.now(tz=datetime.timezone.utc),
                )
            )
            db.commit()
        elif submission_upvote.cancelled:
            db_obj.upvotes_count += 1
            submission_upvote.cancelled = False
            db.commit()
        return db_obj

    def cancel_upvote(
        self, db: Session, *, db_obj: Submission, voter: models.User
    ) -> Submission:
        submission_upvote = (
            db.query(SubmissionUpvotes)
            .filter_by(submission_id=db_obj.id, voter_id=voter.id)
            .first()
        )
        if submission_upvote is not None and not submission_upvote.cancelled:
            db_obj.upvotes_count -= 1
            assert db_obj.upvotes_count >= 0
            submission_upvote.cancelled = True
            db.commit()
            db.refresh(db_obj)
        return db_obj

    def get_all_valid(self, db: Session) -> List[Submission]:
        return db.query(Submission).filter_by(is_hidden=False).all()

    def count_upvotes(self, db: Session, submission: Submission) -> int:
        return (
            db.query(models.SubmissionUpvotes)
            .filter_by(submission_id=submission.id, cancelled=False)
            .count()
        )


submission = CRUDSubmission(Submission)
