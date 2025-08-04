import datetime
import json
from typing import Any, Optional, Union

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.param_functions import Query

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import get_redis_cli, is_dev, report_msg
from chafan_core.app.feed import get_activities, get_random_activities
from chafan_core.app.feed import get_activities_v2
from chafan_core.app.schemas.activity import UserFeedSettings
from chafan_core.app.schemas.answer import AnswerPreview, AnswerPreviewForVisitor
from chafan_core.utils.base import unwrap


import logging
logger = logging.getLogger(__name__)

router = APIRouter()


def _update_feed_seq(
    cached_layer: CachedLayer, s: schemas.FeedSequence, full_answers: bool
) -> schemas.FeedSequence:
    for a in s.activities:
        if hasattr(a.event.content, "answer") and full_answers:
            answer: Union[AnswerPreview, AnswerPreviewForVisitor] = getattr(
                a.event.content, "answer"
            )
            answer.full_answer = cached_layer.get_answer(answer.uuid)
    return s


@router.get("/", response_model=schemas.FeedSequence)
async def get_feed(
    request: Request,
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    before_activity_id: Optional[int] = None,
    limit: int = 20,
    random: bool = Query(default=False),
    full_answers: bool = Query(default=False),
    subject_user_uuid: Optional[str] = None,
) -> Any:
    """
    Get activity feed.
    """
    current_user_id: int = unwrap(cached_layer.principal_id)
    logger.info(f"User {current_user_id} GET activity skip={before_activity_id} limit={limit}, random={random}, full={full_answers}")

    activities = await cached_layer.get_user_activity(
            current_user_id, before_activity_id, limit, subject_user_uuid)
    logger.info(activities)

#    activities = await get_activities_v2(
#            cached_layer = cached_layer,
#        before_activity_id=before_activity_id,
#        limit=limit,
#        receiver_user_id=current_user_id,
#        subject_user_uuid=subject_user_uuid,
#    )
    #logger.info("to call v1 api")
    activities = get_activities(
        before_activity_id=before_activity_id,
        limit=limit,
        receiver_user_id=current_user_id,
        subject_user_uuid=subject_user_uuid,
    )
    #logger.info("call v1 get length : " + str( len(activities) ))
    # 2025-Jul-10 feed table 在测试里一直是空的。下面的 get_random_activities 提供了主界面的动态
    # 感觉这个 logic 是不太对的，但底下的 feed.py 不太好修
    # 我应该去实现一组新的 activities API，用来提供 rss 服务。再回来改原有的 acivities 逻辑
    cache_minutes = 30
    if (
        (before_activity_id is None or random)
        and len(activities) == 0
        and subject_user_uuid is None
    ):
        cache_minutes = 5
        random = True
        activities = get_random_activities(
            receiver_user_id=current_user_id,
            before_activity_id=before_activity_id,
            limit=limit,
        )
    data = schemas.FeedSequence(activities=activities, random=random)
    if not is_dev():
        redis.delete(key)
        redis.set(
            key,
            json.dumps(jsonable_encoder(data)),
            ex=datetime.timedelta(minutes=cache_minutes),
        )
    return _update_feed_seq(cached_layer, data, full_answers=full_answers)


@router.get("/settings", response_model=schemas.UserFeedSettings)
def get_settings(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
) -> Any:
    return cached_layer.get_current_active_user().feed_settings


@router.put("/settings/blocked-origins/", response_model=schemas.GenericResponse)
def update_blocked_origins(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    update_in: schemas.UpdateOrigins,
) -> Any:
    current_user = cached_layer.get_current_active_user()
    if current_user.feed_settings:
        settings = UserFeedSettings.parse_obj(current_user.feed_settings)
    else:
        settings = UserFeedSettings()
    if update_in.action == "add":
        settings.blocked_origins.append(update_in.origin)
    elif update_in.action == "remove":
        settings.blocked_origins.remove(update_in.origin)
    else:
        report_msg("Unknown origin update action: " + update_in.action)
    current_user.feed_settings = jsonable_encoder(settings)
    return schemas.GenericResponse()
