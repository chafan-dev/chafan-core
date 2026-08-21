import datetime
import logging
from typing import Any, Dict, List, Optional, Union

from pydantic.types import SecretStr
from sqlalchemy import desc
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func

from chafan_core.app import karma, rules
from chafan_core.app.config import settings
from chafan_core.app.models.answer import Answer
from chafan_core.app.models.article import Article
from chafan_core.app.models.article_column import ArticleColumn
from chafan_core.app.models.question import Question
from chafan_core.app.models.submission import Submission
from chafan_core.app.models.topic import Topic
from chafan_core.app.models.user import User
from chafan_core.app.schemas.security import IntlPhoneNumber
from chafan_core.app.schemas.user import UserCreate, UserUpdate
from chafan_core.app.security import get_password_hash, verify_password
from chafan_core.utils.base import get_uuid
from chafan_core.utils.validators import StrippedNonEmptyBasicStr

logger = logging.getLogger(__name__)


def get(db: Session, id: Any) -> Optional[User]:
    return db.query(User).filter(User.id == id).first()


def get_by_uuid(db: Session, *, uuid: str) -> Optional[User]:
    return db.query(User).filter_by(uuid=uuid).first()


def get_by_email(db: Session, *, email: str) -> Optional[User]:
    return db.query(User).filter_by(email=email).first()


def get_by_phone_number(
    db: Session, *, phone_number: IntlPhoneNumber
) -> Optional[User]:
    return (
        db.query(User)
        .filter_by(
            phone_number_country_code=phone_number.country_code,
            phone_number_subscriber_number=phone_number.subscriber_number,
        )
        .first()
    )


def get_by_handle(db: Session, *, handle: str) -> Optional[User]:
    return db.query(User).filter(User.handle == handle).first()


def get_all_active_users(db: Session) -> List[User]:
    return db.query(User).filter_by(is_active=True).all()


def _get_unique_uuid(db: Session) -> str:
    while True:
        uuid = get_uuid()
        if get_by_uuid(db, uuid=uuid) is None:
            return uuid


def _generate_handle(db: Session, prefix: str) -> str:
    user = get_by_handle(db, handle=prefix)
    if user is None:
        return prefix
    for i in range(1, 10000):
        handle = prefix + "-" + str(i)
        user = get_by_handle(db, handle=handle)
        if user is None:
            return handle
    raise Exception("Handle generation failed")


def _get_ilike(
    db: Session, *, fragment: str, column: Any, limit: int = 5
) -> List[User]:
    same_ones = (
        db.query(User)
        .filter(column.ilike(f"{fragment}"))
        .order_by(desc(func.length(column)))
        .limit(limit)
        .all()
    )
    similar_ones = (
        db.query(User)
        .filter(column.ilike(f"%{fragment}%"))
        .order_by(desc(func.length(column)))
        .limit(limit)
        .all()
    )
    return same_ones + [s for s in similar_ones if s not in same_ones]


def create(db: Session, *, obj_in: UserCreate) -> User:
    if obj_in.handle is None:
        handle = StrippedNonEmptyBasicStr(
            _generate_handle(db, obj_in.email.split("@")[0])
        )
    else:
        handle = obj_in.handle
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    db_obj = User(
        uuid=_get_unique_uuid(db),
        email=obj_in.email,
        hashed_password=get_password_hash(obj_in.password),
        full_name=obj_in.full_name,
        handle=handle,
        is_superuser=obj_in.is_superuser,
        remaining_coins=rules.INITIAL_USER_COINS,
        created_at=utc_now,
    )
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    # Signing up with a full name already fills in one profile field, which is
    # karma under rules.PROFILE_FIELD. Every other profile edit goes through
    # services.me.update_me, which tracks it there.
    karma.record_new(db, db_obj)
    return db_obj


def update(
    db: Session, *, db_obj: User, obj_in: Union[UserUpdate, Dict[str, Any]]
) -> User:
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_none=True)
    if update_data.get("password"):
        hashed_password = get_password_hash(update_data["password"])
        del update_data["password"]
        update_data["hashed_password"] = hashed_password
    for field in update_data:
        if hasattr(db_obj, field):
            setattr(db_obj, field, update_data[field])
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    return db_obj


def authenticate(db: Session, *, email: str, password: SecretStr) -> Optional[User]:
    user = get_by_email(db, email=email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def is_active(user: User) -> bool:
    return user.is_active


def is_superuser(user: User) -> bool:
    return user.is_superuser


def get_superuser(db: Session) -> User:
    user = db.query(User).filter_by(is_superuser=True).first()
    assert user is not None
    return user


def try_get_superuser(db: Session) -> Optional[User]:
    """Like :func:`get_superuser`, but ``None`` instead of an assertion.

    For callers that must not take down their transaction over a missing
    superuser -- see ``services.events._superuser``.
    """
    return db.query(User).filter_by(is_superuser=True).first()


def try_get_visitor_user(db: Session) -> Optional[User]:
    if not settings.VISITOR_USER_ID:
        return None
    return db.query(User).filter_by(id=settings.VISITOR_USER_ID).first()


def add_follower(db: Session, *, db_obj: User, follower: User) -> User:
    if follower not in db_obj.followers:
        db_obj.followers.append(follower)
        db.flush()
        db.refresh(db_obj)
    return db_obj


def remove_follower(db: Session, *, db_obj: User, follower: User) -> User:
    if follower in db_obj.followers:
        db_obj.followers.remove(follower)
        db.flush()
        db.refresh(db_obj)
        assert db_obj not in follower.followed
    return db_obj


def subscribe_question(db: Session, *, db_obj: User, question: Question) -> User:
    if question not in db_obj.subscribed_questions:
        db_obj.subscribed_questions.append(question)
        db.flush()
        db.refresh(db_obj)
        # TODO:
        # db.add(subscribe_question_activity())
        # db.flush()
    return db_obj


def unsubscribe_question(db: Session, *, db_obj: User, question: Question) -> User:
    if question in db_obj.subscribed_questions:
        db_obj.subscribed_questions.remove(question)
        db.flush()
        db.refresh(db_obj)
    return db_obj


def subscribe_submission(db: Session, *, db_obj: User, submission: Submission) -> User:
    if submission not in db_obj.subscribed_submissions:
        db_obj.subscribed_submissions.append(submission)
        db.flush()
        db.refresh(db_obj)
        # TODO:
        # db.add(subscribe_submission_activity())
        # db.flush()
    return db_obj


def unsubscribe_submission(
    db: Session, *, db_obj: User, submission: Submission
) -> User:
    if submission in db_obj.subscribed_submissions:
        db_obj.subscribed_submissions.remove(submission)
        db.flush()
        db.refresh(db_obj)
    return db_obj


def subscribe_article_column(
    db: Session, *, db_obj: User, article_column: ArticleColumn
) -> User:
    if article_column not in db_obj.subscribed_article_columns:
        db_obj.subscribed_article_columns.append(article_column)
        db.flush()
        db.refresh(db_obj)
    return db_obj


def unsubscribe_article_column(
    db: Session, *, db_obj: User, article_column: ArticleColumn
) -> User:
    if article_column in db_obj.subscribed_article_columns:
        db_obj.subscribed_article_columns.remove(article_column)
        db.flush()
        db.refresh(db_obj)
    return db_obj


def bookmark_answer(db: Session, *, db_obj: User, answer: Answer) -> User:
    if answer not in db_obj.bookmarked_answers:
        db_obj.bookmarked_answers.append(answer)
        db.flush()
        db.refresh(db_obj)
    return db_obj


def unbookmark_answer(db: Session, *, db_obj: User, answer: Answer) -> User:
    if answer in db_obj.bookmarked_answers:
        db_obj.bookmarked_answers.remove(answer)
        db.flush()
        db.refresh(db_obj)
    return db_obj


def bookmark_article(db: Session, *, db_obj: User, article: Article) -> User:
    if article not in db_obj.bookmarked_articles:
        db_obj.bookmarked_articles.append(article)
        db.flush()
        db.refresh(db_obj)
    return db_obj


def unbookmark_article(db: Session, *, db_obj: User, article: Article) -> User:
    if article in db_obj.bookmarked_articles:
        db_obj.bookmarked_articles.remove(article)
        db.flush()
        db.refresh(db_obj)
    return db_obj


def subscribe_topic(db: Session, *, db_obj: User, topic: Topic) -> User:
    if topic not in db_obj.subscribed_topics:
        db_obj.subscribed_topics.append(topic)
        db.flush()
        db.refresh(db_obj)
        # TODO:
        # db.add(subscribe_topic_activity())
        # db.flush()
    return db_obj


def unsubscribe_topic(db: Session, *, db_obj: User, topic: Topic) -> User:
    if topic in db_obj.subscribed_topics:
        db_obj.subscribed_topics.remove(topic)
        db.flush()
        db.refresh(db_obj)
    return db_obj


def update_residency_topics(
    db: Session, *, db_obj: User, new_topics: List[Topic]
) -> None:
    for t in new_topics:
        if t in db_obj.residency_topics:
            continue
        db_obj.residency_topics.append(t)
    for t in db_obj.residency_topics:
        if t not in new_topics:
            db_obj.residency_topics.remove(t)
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)


def update_profession_topics(
    db: Session, *, db_obj: User, new_topics: List[Topic]
) -> None:
    for t in new_topics:
        if t in db_obj.profession_topics:
            continue
        db_obj.profession_topics.append(t)
    for t in db_obj.profession_topics:
        if t not in new_topics:
            db_obj.profession_topics.remove(t)
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)


def search_by_handle_or_full_name(db: Session, *, fragment: str) -> List[User]:
    users_by_handle = _get_ilike(db, fragment=fragment, column=User.handle)
    users_by_full_name = _get_ilike(db, fragment=fragment, column=User.full_name)
    return users_by_handle + [u for u in users_by_full_name if u not in users_by_handle]
