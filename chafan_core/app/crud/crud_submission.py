import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.infra.search_index import do_search
from chafan_core.app.models.submission import Submission, SubmissionUpvotes
from chafan_core.app.models.topic import Topic
from chafan_core.app.schemas.submission import SubmissionCreate, SubmissionUpdate
from chafan_core.utils.base import get_uuid


def get(db: Session, id: Any) -> Optional[Submission]:
    return db.query(Submission).filter(Submission.id == id).first()


def get_by_uuid(db: Session, *, uuid: str) -> Optional[Submission]:
    return db.query(Submission).filter_by(uuid=uuid).first()


def _get_unique_uuid(db: Session) -> str:
    while True:
        uuid = get_uuid()
        if get_by_uuid(db, uuid=uuid) is None:
            return uuid


def create_with_author(
    db: Session, *, obj_in: SubmissionCreate, author_id: int
) -> Submission:
    site = crud.site.get_by_uuid(db, uuid=obj_in.site_uuid)
    assert site is not None
    obj_in_data = jsonable_encoder(obj_in)
    del obj_in_data["site_uuid"]
    obj_in_data["site_id"] = site.id
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    db_obj = Submission(
        **obj_in_data,
        uuid=_get_unique_uuid(db),
        author_id=author_id,
        updated_at=utc_now,
        created_at=utc_now,
    )
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    return db_obj


def update_topics(
    db: Session, *, db_obj: Submission, new_topics: List[Topic]
) -> Submission:
    db_obj.topics.clear()
    db_obj.topics = new_topics
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    return db_obj


def search(db: Session, *, q: str) -> List[Submission]:
    ids = do_search("submission", query=q)
    if not ids:
        return []
    ret = []
    for id in ids:
        submission = get(db, id=id)
        if submission:
            ret.append(submission)
    return ret


def upvote(db: Session, *, db_obj: Submission, voter: models.User) -> Submission:
    submission_upvote = (
        db.query(SubmissionUpvotes)
        .filter_by(submission_id=db_obj.id, voter_id=voter.id)
        .first()
    )
    if submission_upvote is None:
        submission_upvote = SubmissionUpvotes(submission=db_obj, voter=voter)
        db.add(submission_upvote)
        db_obj.upvotes_count += 1
        db.flush()
        db.refresh(db_obj)
    elif submission_upvote.cancelled:
        db_obj.upvotes_count += 1
        submission_upvote.cancelled = False
        db.flush()
    return db_obj


def cancel_upvote(db: Session, *, db_obj: Submission, voter: models.User) -> Submission:
    submission_upvote = (
        db.query(SubmissionUpvotes)
        .filter_by(submission_id=db_obj.id, voter_id=voter.id)
        .first()
    )
    if submission_upvote is not None and not submission_upvote.cancelled:
        db_obj.upvotes_count -= 1
        assert db_obj.upvotes_count >= 0
        submission_upvote.cancelled = True
        db.flush()
        db.refresh(db_obj)
    return db_obj


def update(
    db: Session, *, db_obj: Submission, obj_in: Union[SubmissionUpdate, Dict[str, Any]]
) -> Submission:
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


def get_all_valid(db: Session) -> List[Submission]:
    return db.query(Submission).filter_by(is_hidden=False).all()


def count_upvotes(db: Session, submission: Submission) -> int:
    return (
        db.query(models.SubmissionUpvotes)
        .filter_by(submission_id=submission.id, cancelled=False)
        .count()
    )
