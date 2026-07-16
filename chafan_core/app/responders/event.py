"""Event / notification ORM → API schema shaping."""

from __future__ import annotations

import time
from typing import Optional

import sentry_sdk

from chafan_core.app import crud, models, schemas
from chafan_core.app.common import report_msg
from chafan_core.app.schemas import event as event_module
from chafan_core.app.schemas.event import (
    ClaimAnswerQuestionRewardInternal,
    CreateAnswerQuestionRewardInternal,
    Event,
    EventInternal,
)
from chafan_core.app.schemas.notification import Notification, NotificationInDBBase
from chafan_core.app.schemas.reward import AnsweredQuestionCondition, RewardCondition
from chafan_core.utils.base import map_, unwrap

_KEYS = [
    "reward",
    "submission",
    "article",
    "article_column",
    "subject",
    "question",
    "answer",
    "comment",
    "reply",
    "parent_comment",
    "user",
    "site",
    "channel",
    "submission_suggestion",
    "answer_suggest_edit",
]


def materialize_event(mat, event_internal_json: str) -> Optional[Event]:
    try:
        event = EventInternal.parse_raw(event_internal_json)
    except Exception:
        if time.time() % 2 == 0:
            sentry_sdk.capture_message(
                f"Failed to materialize event: {event_internal_json}",
            )
        return None
    db = mat.broker.get_db()
    kwargs = {}
    for k, v in event.content.dict().items():
        if k == "verb":
            kwargs["verb"] = v
        else:
            if k in ("invited_email", "payment_amount", "message"):
                kwargs[k] = v
            else:
                assert k.endswith("_id"), k
                k = k[:-3]
                assert k in _KEYS, k
                if k == "subject" or k == "user":
                    kwargs[k] = map_(crud.user.get(db, id=v), mat.preview_of_user)
                elif k == "question":
                    question = crud.question.get(db, id=v)
                    if question is None:
                        return None
                    question_data = mat.preview_of_question(question)
                    if question_data is None:
                        return None
                    kwargs[k] = question_data
                elif k == "submission":
                    submission = crud.submission.get(db, id=v)
                    if submission is None:
                        return None
                    submission_data = mat.submission_schema_from_orm(submission)
                    if submission_data is None:
                        return None
                    kwargs[k] = submission_data
                elif k == "submission_suggestion":
                    submission_suggestion = crud.submission_suggestion.get(db, id=v)
                    if submission_suggestion is None:
                        return None
                    submission_suggestion_data = (
                        mat.submission_suggestion_schema_from_orm(
                            submission_suggestion
                        )
                    )
                    if submission_suggestion_data is None:
                        return None
                    kwargs[k] = submission_suggestion_data
                elif k == "answer_suggest_edit":
                    answer_suggest_edit = crud.answer_suggest_edit.get(db, id=v)
                    if answer_suggest_edit is None:
                        return None
                    answer_suggest_edit_data = (
                        mat.answer_suggest_edit_schema_from_orm(
                            answer_suggest_edit
                        )
                    )
                    if answer_suggest_edit_data is None:
                        return None
                    kwargs[k] = answer_suggest_edit_data
                elif k == "reward":
                    reward = crud.reward.get(db, id=v)
                    if reward is None:
                        return None
                    kwargs["reward"] = mat.reward_schema_from_orm(reward)
                    if isinstance(
                        event.content, CreateAnswerQuestionRewardInternal
                    ) or isinstance(
                        event.content, ClaimAnswerQuestionRewardInternal
                    ):
                        condition = RewardCondition.parse_obj(reward.condition)
                        assert isinstance(
                            condition.content, AnsweredQuestionCondition
                        )
                        question = crud.question.get_by_uuid(
                            db, uuid=condition.content.question_uuid
                        )
                        assert question is not None
                        question_data = mat.preview_of_question(question)
                        if question_data is None:
                            return None
                        kwargs["question"] = question_data
                elif k == "answer":
                    answer = crud.answer.get(db, id=v)
                    if answer is None:
                        return None
                    assert answer.body is not None
                    answer_preview = mat.preview_of_answer(answer)
                    if answer_preview:
                        kwargs[k] = answer_preview
                    else:
                        return None
                elif k == "article":
                    article = crud.article.get(db, id=v)
                    if article is None:
                        return None
                    data = mat.preview_of_article(article)
                    if data is None:
                        return None
                    else:
                        kwargs[k] = data
                elif k == "article_column":
                    article_column = crud.article_column.get(db, id=v)
                    if article_column is None:
                        return None
                    kwargs[k] = mat.article_column_schema_from_orm(article_column)
                elif k in ["comment", "parent_comment", "reply"]:
                    comment = crud.comment.get(db, id=v)
                    if comment:
                        comment_data = mat.comment_schema_from_orm(comment)
                        if comment_data:
                            kwargs[k] = comment_data
                        else:
                            return None
                elif k == "site":
                    kwargs[k] = map_(
                        crud.site.get(db, id=v), mat.site_schema_from_orm
                    )
                elif k == "channel":
                    kwargs[k] = map_(
                        crud.channel.get(db, id=v), mat.channel_schema_from_orm
                    )
                else:
                    raise Exception(k)
    event_content_class = event.content.__class__.__name__
    if event_content_class.endswith("Internal"):
        new_class = getattr(event_module, event_content_class[: -len("Internal")])
    else:
        new_class = getattr(event_module, event_content_class)
    try:
        return Event(created_at=event.created_at, content=new_class(**kwargs))
    except Exception as e:
        report_msg(
            f"Event construction exception: kwargs={kwargs}, exception={e}, event_internal_json={event_internal_json}"
        )
        return None


def notification_schema_from_orm(mat, notification: models.Notification) -> Optional[Notification]:
    base = NotificationInDBBase.from_orm(notification)
    if notification.event_json:
        event = materialize_event(mat, notification.event_json)
        if event is None:
            return None
        d = base.dict()
        d["event"] = event
        return Notification(**d)
    return None
