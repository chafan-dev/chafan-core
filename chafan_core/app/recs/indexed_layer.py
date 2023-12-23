import datetime
from typing import List, Optional, Union

from chafan_core.app import crud, models, schemas
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import run_dramatiq_task
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.task import (
    refresh_interesting_question_ids_for_user,
    refresh_interesting_user_ids_for_user,
)
from chafan_core.utils.base import filter_not_none, get_utc_now, unwrap


def days_in_seconds(days: int) -> int:
    return days * 24 * 60 * 60


def _is_expired(updated_at: Optional[datetime.datetime], ttl_seconds: int) -> bool:
    if not updated_at:
        return True
    duration = get_utc_now() - updated_at
    return duration.total_seconds() > ttl_seconds


def _get_interesting_question_ids(user: models.User) -> List[int]:
    # if way too old, refresh now
    if _is_expired(user.interesting_question_ids_updated_at, days_in_seconds(7)):
        refresh_interesting_question_ids_for_user(user.id)
    # if a bit old, enqueue refresh task
    elif _is_expired(user.interesting_question_ids_updated_at, days_in_seconds(3)):
        run_dramatiq_task(refresh_interesting_question_ids_for_user, user.id)

    # return latest version
    if user.interesting_question_ids is None:
        return []
    return user.interesting_question_ids


def get_interesting_questions(
    cached_layer: CachedLayer,
) -> Union[List[schemas.QuestionPreview], List[schemas.QuestionPreviewForVisitor]]:
    current_user = cached_layer.try_get_current_user()
    if not current_user:
        visitor = crud.user.try_get_visitor_user(cached_layer.get_db())
        if not visitor:
            return []
        return filter_not_none(
            [
                cached_layer.materializer.preview_of_question_for_visitor(
                    unwrap(crud.question.get(cached_layer.get_db(), id=q_id))
                )
                for q_id in _get_interesting_question_ids(visitor)
            ]
        )
    else:
        return filter_not_none(
            [
                cached_layer.materializer.preview_of_question(
                    unwrap(crud.question.get(cached_layer.get_db(), id=q_id))
                )
                for q_id in _get_interesting_question_ids(current_user)
            ]
        )


def _get_interesting_user_ids(user: models.User) -> List[int]:
    # if way too old, refresh now
    if _is_expired(user.interesting_user_ids_updated_at, days_in_seconds(7)):
        refresh_interesting_user_ids_for_user(user.id)
    # if a bit old, enqueue refresh task
    elif _is_expired(user.interesting_user_ids_updated_at, days_in_seconds(3)):
        run_dramatiq_task(refresh_interesting_user_ids_for_user, user.id)

    # return latest version
    if user.interesting_user_ids is None:
        return []
    return user.interesting_user_ids


def get_interesting_users(cached_layer: CachedLayer) -> List[UserPreview]:
    current_user = cached_layer.try_get_current_user()
    if not current_user:
        current_user = crud.user.try_get_visitor_user(cached_layer.get_db())
    if current_user:
        return [
            cached_layer.preview_of_user(
                unwrap(crud.user.get(cached_layer.get_db(), id=u))
            )
            for u in _get_interesting_user_ids(current_user)
        ]
    return []


def force_refresh_all_interesting_users(broker: DataBroker) -> None:
    for u in crud.user.get_all_active_users(broker.get_db()):
        refresh_interesting_user_ids_for_user(u.id)


def force_refresh_all_interesting_questions(broker: DataBroker) -> None:
    for u in crud.user.get_all_active_users(broker.get_db()):
        refresh_interesting_question_ids_for_user(u.id)
