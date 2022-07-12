import datetime
from typing import Iterable, NoReturn, Optional

from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.activity import Activity
from chafan_core.app.schemas.event import (
    AnswerQuestionInternal,
    CreateArticleInternal,
    CreateSubmissionInternal,
    EventInternal,
    FollowUserInternal,
    SubscribeArticleColumnInternal,
    UpvoteAnswerInternal,
    UpvoteArticleInternal,
    UpvoteQuestionInternal,
    UpvoteSubmissionInternal,
)


class CRUDActivity(CRUDBase[Activity, NoReturn, NoReturn]):
    def get_multi_by_id_range(
        self, db: Session, *, min_id: int, max_id: Optional[int],
    ) -> Iterable[Activity]:
        stream = db.query(Activity)
        if max_id is not None:
            stream = stream.filter(Activity.id.between(min_id, max_id - 1))
        else:
            stream = stream.filter(Activity.id > min_id)
        stream = stream.order_by(Activity.created_at.desc())
        return stream

    def count(self, db: Session) -> int:
        return db.query(Activity).count()


def create_submission_activity(
    *, submission: models.Submission, site: models.Site, created_at: datetime.datetime
) -> Activity:
    return Activity(
        created_at=created_at,
        site_id=site.id,
        event_json=EventInternal(
            created_at=created_at,
            content=CreateSubmissionInternal(
                subject_id=submission.author.id, submission_id=submission.id,
            ),
        ).json(),
    )


def create_article_activity(
    *, article: models.Article, created_at: datetime.datetime
) -> Activity:
    return Activity(
        created_at=created_at,
        site_id=None,
        event_json=EventInternal(
            created_at=created_at,
            content=CreateArticleInternal(
                subject_id=article.author.id, article_id=article.id,
            ),
        ).json(),
    )


def create_answer_activity(
    *, answer: models.Answer, site_id: int, created_at: datetime.datetime
) -> Activity:
    return Activity(
        created_at=created_at,
        site_id=site_id,
        event_json=EventInternal(
            created_at=created_at,
            content=AnswerQuestionInternal(
                subject_id=answer.author.id, answer_id=answer.id,
            ),
        ).json(),
    )


def upvote_answer_activity(
    *,
    voter: models.User,
    answer: models.Answer,
    site_id: int,
    created_at: datetime.datetime,
) -> Activity:
    return Activity(
        created_at=created_at,
        site_id=site_id,
        event_json=EventInternal(
            created_at=created_at,
            content=UpvoteAnswerInternal(subject_id=voter.id, answer_id=answer.id,),
        ).json(),
    )


def upvote_article_activity(
    *, voter: models.User, article: models.Article, created_at: datetime.datetime,
) -> Activity:
    return Activity(
        created_at=created_at,
        site_id=None,
        event_json=EventInternal(
            created_at=created_at,
            content=UpvoteArticleInternal(subject_id=voter.id, article_id=article.id,),
        ).json(),
    )


def upvote_question_activity(
    *,
    voter: models.User,
    question: models.Question,
    site_id: int,
    created_at: datetime.datetime,
) -> Activity:
    return Activity(
        created_at=created_at,
        site_id=site_id,
        event_json=EventInternal(
            created_at=created_at,
            content=UpvoteQuestionInternal(
                subject_id=voter.id, question_id=question.id,
            ),
        ).json(),
    )


def upvote_submission_activity(
    *,
    voter: models.User,
    submission: models.Submission,
    site_id: int,
    created_at: datetime.datetime,
) -> Activity:
    return Activity(
        created_at=created_at,
        site_id=site_id,
        event_json=EventInternal(
            created_at=created_at,
            content=UpvoteSubmissionInternal(
                subject_id=voter.id, submission_id=submission.id,
            ),
        ).json(),
    )


def follow_user_activity(
    *, follower: models.User, followed: models.User, created_at: datetime.datetime
) -> Activity:
    return Activity(
        created_at=created_at,
        event_json=EventInternal(
            created_at=created_at,
            content=FollowUserInternal(subject_id=follower.id, user_id=followed.id,),
        ).json(),
    )


def subscribe_article_column_activity(
    *,
    user: models.User,
    article_column: models.ArticleColumn,
    created_at: datetime.datetime,
) -> Activity:
    return Activity(
        created_at=created_at,
        event_json=EventInternal(
            created_at=created_at,
            content=SubscribeArticleColumnInternal(
                subject_id=user.id, article_column_id=article_column.id,
            ),
        ).json(),
    )


activity = CRUDActivity(Activity)
