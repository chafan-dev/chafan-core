import datetime
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

from pydantic.types import SecretStr
from sqlalchemy.orm import Session

from chafan_core.app.common import is_dev
from chafan_core.app.config import settings
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.crud.crud_activity import (
    follow_user_activity,
    subscribe_article_column_activity,
)
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
from chafan_core.utils.validators import StrippedNonEmptyBasicStr


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def get_by_email(self, db: Session, *, email: str) -> Optional[User]:
        return db.query(User).filter_by(email=email).first()

    def get_by_telegram_id(self, db: Session, *, telegram_id: str) -> Optional[User]:
        return db.query(User).filter_by(verified_telegram_user_id=telegram_id).first()

    def get_by_phone_number(
        self, db: Session, *, phone_number: IntlPhoneNumber
    ) -> Optional[User]:
        return (
            db.query(User)
            .filter_by(
                phone_number_country_code=phone_number.country_code,
                phone_number_subscriber_number=phone_number.subscriber_number,
            )
            .first()
        )

    def _generate_handle(self, db: Session, prefix: str) -> str:
        user = self.get_by_handle(db, handle=prefix)
        if user is None:
            return prefix
        for i in range(1, 10000):
            handle = prefix + "-" + str(i)
            user = self.get_by_handle(db, handle=handle)
            if user is None:
                return handle
        raise Exception("Handle generation failed")

    def get_by_handle(self, db: Session, *, handle: str) -> Optional[User]:
        return db.query(User).filter(User.handle == handle).first()

    def get_all_active_users(self, db: Session) -> List[User]:
        return db.query(User).filter_by(is_active=True).all()

    # 2025-Dec-11 This function is synchronized for now. We define it as async to facilitate further improvement
    async def create(self, db: Session, *, obj_in: UserCreate) -> User:
        if obj_in.handle is None:
            handle = StrippedNonEmptyBasicStr(
                self._generate_handle(db, obj_in.email.split("@")[0])
            )
        else:
            handle = obj_in.handle
        initial_coins = 0
        if is_dev():
            initial_coins = 100
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        db_obj = User(
            uuid=self.get_unique_uuid(db),
            email=obj_in.email,
            hashed_password=get_password_hash(obj_in.password),
            full_name=obj_in.full_name,
            handle=handle,
            is_superuser=obj_in.is_superuser,
            remaining_coins=initial_coins,
            created_at=utc_now,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self, db: Session, *, db_obj: User, obj_in: Union[UserUpdate, Dict[str, Any]]
    ) -> User:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_none=True)
        if update_data.get("password"):
            hashed_password = get_password_hash(update_data["password"])
            del update_data["password"]
            update_data["hashed_password"] = hashed_password
        return super().update(db, db_obj=db_obj, obj_in=update_data)

    def authenticate(
        self, db: Session, *, email: str, password: SecretStr
    ) -> Optional[User]:
        user = self.get_by_email(db, email=email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def is_active(self, user: User) -> bool:
        return user.is_active

    def is_superuser(self, user: User) -> bool:
        return user.is_superuser

    def get_superuser(self, db: Session) -> User:
        user = db.query(User).filter_by(is_superuser=True).first()
        assert user is not None
        return user

    def try_get_visitor_user(self, db: Session) -> Optional[User]:
        if not settings.VISITOR_USER_ID:
            return None
        return db.query(User).filter_by(id=settings.VISITOR_USER_ID).first()

    def add_follower(self, db: Session, *, db_obj: User, follower: User) -> User:
        if follower not in db_obj.followers:
            db_obj.followers.append(follower)
            db.commit()
            db.refresh(db_obj)
            db.add(
                follow_user_activity(
                    follower=follower,
                    followed=db_obj,
                    created_at=datetime.datetime.now(tz=datetime.timezone.utc),
                )
            )
            db.commit()
        return db_obj

    def remove_follower(self, db: Session, *, db_obj: User, follower: User) -> User:
        if follower in db_obj.followers:
            db_obj.followers.remove(follower)
            db.commit()
            db.refresh(db_obj)
            assert db_obj not in follower.followed
        return db_obj

    def subscribe_question(
        self, db: Session, *, db_obj: User, question: Question
    ) -> User:
        if question not in db_obj.subscribed_questions:
            db_obj.subscribed_questions.append(question)
            db.commit()
            db.refresh(db_obj)
            # TODO:
            # db.add(subscribe_question_activity())
            # db.commit()
        return db_obj

    def unsubscribe_question(
        self, db: Session, *, db_obj: User, question: Question
    ) -> User:
        if question in db_obj.subscribed_questions:
            db_obj.subscribed_questions.remove(question)
            db.commit()
            db.refresh(db_obj)
        return db_obj

    def subscribe_submission(
        self, db: Session, *, db_obj: User, submission: Submission
    ) -> User:
        if submission not in db_obj.subscribed_submissions:
            db_obj.subscribed_submissions.append(submission)
            db.commit()
            db.refresh(db_obj)
            # TODO:
            # db.add(subscribe_submission_activity())
            # db.commit()
        return db_obj

    def unsubscribe_submission(
        self, db: Session, *, db_obj: User, submission: Submission
    ) -> User:
        if submission in db_obj.subscribed_submissions:
            db_obj.subscribed_submissions.remove(submission)
            db.commit()
            db.refresh(db_obj)
        return db_obj

    def subscribe_article_column(
        self, db: Session, *, db_obj: User, article_column: ArticleColumn
    ) -> User:
        if article_column not in db_obj.subscribed_article_columns:
            db_obj.subscribed_article_columns.append(article_column)
            db.add(
                subscribe_article_column_activity(
                    user=db_obj,
                    article_column=article_column,
                    created_at=datetime.datetime.now(tz=datetime.timezone.utc),
                )
            )
            db.commit()
            db.refresh(db_obj)
        return db_obj

    def unsubscribe_article_column(
        self, db: Session, *, db_obj: User, article_column: ArticleColumn
    ) -> User:
        if article_column in db_obj.subscribed_article_columns:
            db_obj.subscribed_article_columns.remove(article_column)
            db.commit()
            db.refresh(db_obj)
        return db_obj

    def bookmark_answer(self, db: Session, *, db_obj: User, answer: Answer) -> User:
        if answer not in db_obj.bookmarked_answers:
            db_obj.bookmarked_answers.append(answer)
            db.commit()
            db.refresh(db_obj)
        return db_obj

    def unbookmark_answer(self, db: Session, *, db_obj: User, answer: Answer) -> User:
        if answer in db_obj.bookmarked_answers:
            db_obj.bookmarked_answers.remove(answer)
            db.commit()
            db.refresh(db_obj)
        return db_obj

    def bookmark_article(self, db: Session, *, db_obj: User, article: Article) -> User:
        if article not in db_obj.bookmarked_articles:
            db_obj.bookmarked_articles.append(article)
            db.commit()
            db.refresh(db_obj)
        return db_obj

    def unbookmark_article(
        self, db: Session, *, db_obj: User, article: Article
    ) -> User:
        if article in db_obj.bookmarked_articles:
            db_obj.bookmarked_articles.remove(article)
            db.commit()
            db.refresh(db_obj)
        return db_obj

    def subscribe_topic(self, db: Session, *, db_obj: User, topic: Topic) -> User:
        if topic not in db_obj.subscribed_topics:
            db_obj.subscribed_topics.append(topic)
            db.commit()
            db.refresh(db_obj)
            # TODO:
            # db.add(subscribe_topic_activity())
            # db.commit()
        return db_obj

    def unsubscribe_topic(self, db: Session, *, db_obj: User, topic: Topic) -> User:
        if topic in db_obj.subscribed_topics:
            db_obj.subscribed_topics.remove(topic)
            db.commit()
            db.refresh(db_obj)
        return db_obj

    def update_residency_topics(
        self, db: Session, *, db_obj: User, new_topics: List[Topic]
    ) -> None:
        for t in new_topics:
            if t in db_obj.residency_topics:
                continue
            db_obj.residency_topics.append(t)
        for t in db_obj.residency_topics:
            if t not in new_topics:
                db_obj.residency_topics.remove(t)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)

    def update_profession_topics(
        self, db: Session, *, db_obj: User, new_topics: List[Topic]
    ) -> None:
        for t in new_topics:
            if t in db_obj.profession_topics:
                continue
            db_obj.profession_topics.append(t)
        for t in db_obj.profession_topics:
            if t not in new_topics:
                db_obj.profession_topics.remove(t)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)

    def search_by_handle_or_full_name(
        self, db: Session, *, fragment: str
    ) -> List[User]:
        users_by_handle = self.get_ilike(db, fragment=fragment, column=User.handle)
        users_by_full_name = self.get_ilike(
            db, fragment=fragment, column=User.full_name
        )
        return users_by_handle + [
            u for u in users_by_full_name if u not in users_by_handle
        ]


user = CRUDUser(User)
