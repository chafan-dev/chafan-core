import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.infra.search_index import do_search
from chafan_core.app.models.answer import Answer, Answer_Upvotes
from chafan_core.app.models.user import User
from chafan_core.app.schemas.answer import AnswerCreate, AnswerUpdate
from chafan_core.utils.base import get_uuid


def get(db: Session, id: Any) -> Optional[Answer]:
    return db.query(Answer).filter(Answer.id == id).first()


def get_by_id(db: Session, *, uid: int) -> Optional[Answer]:
    return db.query(Answer).filter_by(id=uid).first()


def get_by_uuid(db: Session, *, uuid: str) -> Optional[Answer]:
    return db.query(Answer).filter_by(uuid=uuid).first()


def _get_unique_uuid(db: Session) -> str:
    while True:
        uuid = get_uuid()
        if get_by_uuid(db, uuid=uuid) is None:
            return uuid


def get_one_as_search_result(db: Session, id: int) -> Optional[Answer]:
    answer = db.query(Answer).filter_by(id=id).first()
    if not answer or answer.is_hidden_by_moderator:
        return None
    if not answer.is_published:
        return None
    return answer


def create_with_author(
    db: Session, *, obj_in: AnswerCreate, author_id: int, site_id: int
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

    db_obj = Answer(
        **obj_in_data,
        author_id=author_id,
        site_id=site_id,
        updated_at=utc_now,
        uuid=_get_unique_uuid(db),
    )
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    db.flush()
    return db_obj


def upvote(db: Session, *, db_obj: Answer, voter: User) -> Answer:
    answer_upvote = (
        db.query(Answer_Upvotes)
        .filter_by(answer_id=db_obj.id, voter_id=voter.id)
        .first()
    )
    if answer_upvote is None:
        answer_upvote = Answer_Upvotes(answer=db_obj, voter=voter)
        db.add(answer_upvote)
        db_obj.upvotes_count += 1
        db.flush()
        db.refresh(db_obj)
    elif answer_upvote.cancelled:
        db_obj.upvotes_count += 1
        answer_upvote.cancelled = False
        db.flush()
    return db_obj


def cancel_upvote(db: Session, *, db_obj: Answer, voter: User) -> Answer:
    answer_upvote = (
        db.query(Answer_Upvotes)
        .filter_by(answer_id=db_obj.id, voter_id=voter.id)
        .first()
    )
    if answer_upvote is not None and not answer_upvote.cancelled:
        db_obj.upvotes_count -= 1
        assert db_obj.upvotes_count >= 0
        answer_upvote.cancelled = True
        db.flush()
        db.refresh(db_obj)
    return db_obj


def search(db: Session, *, q: str) -> List[Answer]:
    ids = do_search("answer", query=q)
    if ids is None:
        # Search index unavailable (e.g. local dev): fall back to listing all.
        return get_all_published(db)
    ret = []
    for id in ids:
        answer = get_one_as_search_result(db, id=id)
        if answer:
            ret.append(answer)
    return ret


def update(
    db: Session, *, db_obj: Answer, obj_in: Union[AnswerUpdate, Dict[str, Any]]
) -> Answer:
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


def update_checked(db: Session, *, db_obj: Answer, obj_in: Dict[str, Any]) -> Answer:
    if db_obj.is_published and "is_published" in obj_in:
        assert obj_in["is_published"]
    return update(db, db_obj=db_obj, obj_in=obj_in)


def delete_forever(db: Session, *, answer: Answer) -> None:
    answer.is_deleted = True
    answer.body = "[DELETED]"
    answer.body_draft = "[DELETED]"
    answer.body_prerendered_text = "[DELETED]"
    for archive in answer.archives:
        archive.body = "[DELETED]"
    db.add(answer)
    db.flush()


def get_all_published(db: Session) -> List[Answer]:
    return db.query(Answer).filter_by(is_deleted=False, is_published=True).all()


def get_all(db: Session) -> List[Answer]:
    return db.query(Answer).all()
