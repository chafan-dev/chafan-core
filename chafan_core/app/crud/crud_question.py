import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.infra.search_index import do_search
from chafan_core.app.models.question import Question, QuestionUpvotes
from chafan_core.app.models.topic import Topic
from chafan_core.app.schemas.question import QuestionCreate, QuestionUpdate
from chafan_core.utils.base import get_uuid


def get(db: Session, id: Any) -> Optional[Question]:
    return db.query(Question).filter(Question.id == id).first()


def get_by_id(db: Session, *, id: int) -> Optional[Question]:
    return db.query(Question).filter(Question.id == id).first()


def get_by_uuid(db: Session, *, uuid: str) -> Optional[Question]:
    return db.query(Question).filter_by(uuid=uuid).first()


def _get_unique_uuid(db: Session) -> str:
    while True:
        uuid = get_uuid()
        if get_by_uuid(db, uuid=uuid) is None:
            return uuid


def create_with_author(
    db: Session, *, obj_in: QuestionCreate, author_id: int
) -> Question:
    site = crud.site.get_by_uuid(db, uuid=obj_in.site_uuid)
    assert site is not None
    obj_in_data = jsonable_encoder(obj_in)
    del obj_in_data["site_uuid"]
    obj_in_data["site_id"] = site.id
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    db_obj = Question(
        **obj_in_data,
        uuid=_get_unique_uuid(db),
        author_id=author_id,
        editor_id=author_id,
        updated_at=utc_now,
        created_at=utc_now,
    )
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    return db_obj


def update_topics(
    db: Session, *, db_obj: Question, new_topics: List[Topic]
) -> Question:
    db_obj.topics.clear()
    db_obj.topics = new_topics
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    return db_obj


def search(db: Session, *, q: str) -> List[Question]:
    ids = do_search("question", query=q)
    if ids is None:
        # Search index unavailable (e.g. local dev): fall back to listing all.
        return get_all_valid(db)
    ret = []
    for id in ids:
        question = get(db, id=id)
        if question:
            ret.append(question)
    return ret


def get_placed_at_home(db: Session) -> List[Question]:
    return db.query(Question).filter_by(is_placed_at_home=True).all()


def upvote(db: Session, *, db_obj: Question, voter: models.User) -> Question:
    question_upvote = (
        db.query(QuestionUpvotes)
        .filter_by(question_id=db_obj.id, voter_id=voter.id)
        .first()
    )
    if question_upvote is None:
        question_upvote = QuestionUpvotes(question=db_obj, voter=voter)
        db.add(question_upvote)
        db_obj.upvotes_count += 1
        db.flush()
        db.refresh(db_obj)
    elif question_upvote.cancelled:
        db_obj.upvotes_count += 1
        question_upvote.cancelled = False
        db.flush()
    return db_obj


def cancel_upvote(db: Session, *, db_obj: Question, voter: models.User) -> Question:
    question_upvote = (
        db.query(QuestionUpvotes)
        .filter_by(question_id=db_obj.id, voter_id=voter.id)
        .first()
    )
    if question_upvote is not None and not question_upvote.cancelled:
        db_obj.upvotes_count -= 1
        assert db_obj.upvotes_count >= 0
        question_upvote.cancelled = True
        db.flush()
        db.refresh(db_obj)
    return db_obj


def update(
    db: Session, *, db_obj: Question, obj_in: Union[QuestionUpdate, Dict[str, Any]]
) -> Question:
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


def get_all_valid(db: Session) -> List[Question]:
    return db.query(Question).filter_by(is_hidden=False).all()
