from chafan_core.app.infra.request_context import RequestContext
from typing import List, Optional

from chafan_core.db.base_class import Base as BaseCrudModel
from chafan_core.app import crud, models, schemas
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.schemas.activity import UserFeedSettings
from chafan_core.app.schemas.event import (
    AnswerQuestionInternal,
    CreateArticleInternal,
    CreateQuestionInternal,
    EventInternal,
)
from chafan_core.app.infra.runtime import execute_with_broker
from chafan_core.utils.base import map_, unwrap

import logging
logger = logging.getLogger(__name__)


def is_blocked(
    activity: schemas.Activity, settings: Optional[schemas.UserFeedSettings]
) -> bool:
    if not settings:
        return False
    if not activity.origins:
        return False
    for origin in activity.origins:
        if origin in settings.blocked_origins:
            return True
    return False


def materialize_activity(
    data_broker: RequestContext,
    activity: models.Activity,
    receiver_id: int,
    feed_settings: Optional[UserFeedSettings],
) -> Optional[schemas.Activity]:
    materializer = data_broker.as_principal(receiver_id)
    output_event = materializer.materialize_event(unwrap(activity.event_json))
    if output_event:
        origins = []
        if activity.site:
            origins.append(schemas.OriginSite(subdomain=activity.site.subdomain))
        activity_data = schemas.Activity(
            id=activity.id,
            site=map_(activity.site, materializer.site_schema_from_orm),
            created_at=activity.created_at,
            verb=output_event.content.verb,
            event=output_event,
            origins=origins,
        )
        if not is_blocked(activity_data, feed_settings):
            return activity_data
    return None

# This is not good OOP practice, but doing it here can avoid making event.py too complex. 2025-Aug-13
def retrieve_content(event: EventInternal, ctx) -> Optional[BaseCrudModel]:
    assert isinstance(event, EventInternal)
    from chafan_core.app.services import answers as answers_service
    from chafan_core.app.services import articles as articles_service
    from chafan_core.app.services import questions as questions_service

    db = ctx.get_db()
    c = event.content
    if isinstance(c, CreateQuestionInternal):
        question = questions_service.get_question_by_id(db, c.question_id)
        if question is None:
            return None
        if question.is_hidden:
            logger.warning("Skip a hidden question: " + str(question))
            return None
        return question
    if isinstance(c, AnswerQuestionInternal):
        answer = answers_service.get_answer_by_id(db, c.answer_id)
        if answer is None:
            return None
        if (answer.is_hidden_by_moderator) or \
            (not answer.is_published):
            logger.warning("Skip a hidden answer: " + str(answer))
            return None
        return answer
    if isinstance(c, CreateArticleInternal):
        article = articles_service.get_article_by_id(db, c.article_id)
        if article is None:
            return None
        if article.is_deleted or (not article.is_published):
            # This branch used to have no check at all, unlike the two above.
            # Activity rows written for drafts before that emitter was removed
            # are still in the table, and this is what keeps them from
            # dereferencing here.
            logger.warning("Skip a hidden article: " + str(article))
            return None
        return article

    logger.error(f"Not supported event type: {event}")
    return None #TODO throw exception

def get_content_from_eventjson(
        ctx: "RequestContext",
        event_json: str) -> Optional[BaseCrudModel]:
    event = EventInternal.parse_raw(event_json)
    content = retrieve_content(event, ctx)
    return content

def get_site_activities(
    ctx: "RequestContext",
    site,
    limit: int,
    all_sites = False) -> List[BaseCrudModel]:
    """The content (questions/answers/articles) behind a site's recent activities."""
    db = ctx.get_db()
    if (site is None) and (not all_sites):
        raise ValueError("site not found ")
    if (not all_sites) and (not site.public_readable):
        raise ValueError("site not allowed ")
    activities = db.query(models.Activity)
    if not all_sites:
        activities = activities.filter_by(site_id=site.id)
    activities = activities.order_by(models.Activity.id.desc()).limit(limit)
    contents = []
    for activity in activities:
        obj = get_content_from_eventjson(ctx, activity.event_json)
        if obj is not None:
            assert isinstance(obj, BaseCrudModel)
            contents.append(obj)
    return contents

def get_activities_v2(
    *,
    ctx: "RequestContext",
    before_activity_id: Optional[int],
    limit: int,
    receiver_user_id: int,
    subject_user_uuid: Optional[str],
) -> List[schemas.Activity]:
    db = ctx.get_db()
    receiver = crud.user.get(db, id=receiver_user_id)
    assert receiver is not None
    # TODO: honor receiver.feed_settings.blocked_origins here. `is_blocked` and
    # the two /activities/settings endpoints are still live, so a user can mute
    # a site, see the setting persist, and keep seeing that site -- this branch
    # is where that promise is dropped. The now-dead v1 `get_activities` below
    # shows the three lines it takes. Not switched on blind: anyone holding a
    # mute from before the v2 rewrite would silently lose feed content on
    # deploy, so size it first with
    #   SELECT count(*) FROM "user" WHERE feed_settings IS NOT NULL
    #     AND feed_settings::jsonb -> 'blocked_origins' <> '[]'::jsonb;
    # and decide between restoring the feature and deleting it.
    feeds = db.query(models.Feed)
    if subject_user_uuid is not None:
        feeds = feeds.filter_by(subject_user_uuid=subject_user_uuid)
    else:
        feeds = feeds.filter_by(receiver_id=receiver_user_id)
    if before_activity_id:
        feeds = feeds.filter(models.Feed.activity_id < before_activity_id)
    feeds = feeds.order_by(models.Feed.activity_id.desc()).limit(limit * 2) # Do we have better idea?
    activities = []
    activity_ids = set()
    for feed in feeds:
        feed_settings = None  # TODO: see the blocked_origins note above.
        if feed.activity_id in activity_ids:
            continue
        activity = materialize_activity(
            ctx.broker, feed.activity, receiver_user_id, feed_settings
        )
        if activity:
            activity_ids.add(feed.activity_id)
            activities.append(activity)
        if len(activities) >= limit:
            break
    logger.info("v2 get " + str(len(activities)))
    return activities


def get_activities( # TODO to remove this function
    *,
    before_activity_id: Optional[int],
    limit: int,
    receiver_user_id: int,
    subject_user_uuid: Optional[str],
) -> List[schemas.Activity]:
    def runnable(broker: RequestContext) -> List[schemas.Activity]:
        db = broker.get_db()
        receiver = crud.user.get(db, id=receiver_user_id)
        assert receiver is not None, receiver_user_id
        if receiver.uuid == subject_user_uuid:
            receiver_id = crud.user.get_superuser(db).id
        else:
            receiver_id = receiver_user_id
        feed_settings = None
        if receiver.feed_settings:
            feed_settings = UserFeedSettings.parse_obj(receiver.feed_settings)
        activities = []
        feeds = db.query(models.Feed).filter_by(receiver_id=receiver_id)
        if before_activity_id:
            feeds = feeds.filter(models.Feed.activity_id < before_activity_id)
        if subject_user_uuid:
            feeds = feeds.filter_by(subject_user_uuid=subject_user_uuid)
        feeds = feeds.order_by(models.Feed.activity_id.desc()).limit(limit)
        for feed in feeds:
            activity = materialize_activity(
                broker, feed.activity, receiver_user_id, feed_settings
            )
            if activity:
                activities.append(activity)
        return activities

    data = execute_with_broker(runnable)
    if data:
        return data
    else:
        return []



