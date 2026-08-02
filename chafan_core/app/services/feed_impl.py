from chafan_core.app.infra.request_context import RequestContext
from typing import Dict, List, NamedTuple, Optional, Set

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
from chafan_core.app.services.activity_policy import (
    ALWAYS_PUBLIC_EVENT_VERBS,
    Audience,
    feed_audience_of,
)
from chafan_core.app.infra.runtime import execute_with_broker
from chafan_core.utils.base import map_, unwrap

import logging
logger = logging.getLogger(__name__)


class ActivityDistributionInfo(NamedTuple):
    receiver_ids: Set[int]
    subject_user_uuid: Optional[str]




def lookup_activity_receiver_list(broker: RequestContext, activity: models.Activity)->ActivityDistributionInfo:
    """Resolve who receives a Feed row for ``activity``.

    The audience per verb comes from :data:`activity_policy.POLICY`; see that
    module for the full matrix and for the v1 rules that are recorded there
    but not yet applied.
    """
    try:
        event = EventInternal.parse_raw(activity.event_json)
    except Exception:
        logger.error("failed to parse Event " + activity.event_json)
        return ActivityDistributionInfo(receiver_ids=set(), subject_user_uuid=None)
    logger.info(f"get event: {event}")
    audience = feed_audience_of(event.content.verb)
    if audience is None:
        # No verb reaching fan-out today has a null audience; if one does, the
        # policy table is the place to add it.
        logger.warning(
            "no feed audience for verb %s; activity %s not fanned out",
            event.content.verb,
            activity.id,
        )
        return ActivityDistributionInfo(receiver_ids=set(), subject_user_uuid=None)
    assert audience is Audience.SUBJECT_FOLLOWERS, audience
    assert hasattr(event.content, "subject_id")
    read_db = broker.get_db()
    subject = crud.user.get(read_db, id=event.content.subject_id)
    assert subject is not None
    subject_user_uuid = subject.uuid
    receivers: Dict[int, models.User] = {}
    for follower in subject.followers:
        receivers[follower.id] = follower
    # TODO didn't consider blocker setting 2025-07-19
    return ActivityDistributionInfo(
        receiver_ids=set(receivers.keys()), subject_user_uuid=subject_user_uuid
    )

def new_activity_into_feed(broker: RequestContext, activity:models.Activity) -> None:
    logger.info("generating feed for activity "  + str(activity.id))
    assert activity.id is not None
    assert isinstance(activity.id, int)
    receivers = lookup_activity_receiver_list(broker, activity)
    write_db = broker.get_db()
    for receiver_id in receivers.receiver_ids:
        feed = write_db.query(models.Feed)  \
            .filter_by(receiver_id=receiver_id, activity_id=activity.id) \
            .first()
        if feed is None:
            write_db.add(
                models.Feed(
                    receiver_id=receiver_id,
                    activity_id=activity.id,
                    subject_user_uuid=receivers.subject_user_uuid,
                )
            )



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
        return articles_service.get_article_by_id(db, c.article_id)

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
    # TODO feed_settings not supported yet
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
        feed_settings = None # TODO not supported yed
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


def _is_public_activity(activity: schemas.Activity) -> bool:
    if activity.site and activity.site.public_readable:
        return True
    return activity.event.content.verb in ALWAYS_PUBLIC_EVENT_VERBS


def get_random_activities(
    *, receiver_user_id: int, before_activity_id: Optional[int], limit: int
) -> List[schemas.Activity]:
    id_bucket = receiver_user_id % 10

    def runnable(broker: RequestContext) -> List[schemas.Activity]:
        db = broker.get_db()
        stream = db.query(models.Activity)
        if before_activity_id is not None:
            stream = stream.filter(models.Activity.id < before_activity_id)
        stream = stream.filter(models.Activity.id % 10 != id_bucket).order_by(
            models.Activity.id.desc()
        )
        activities: List[schemas.Activity] = []
        for activity in stream:
            materialized_activity = materialize_activity(
                broker, activity, receiver_user_id, None
            )
            if len(activities) >= limit:
                break
            if materialized_activity and _is_public_activity(materialized_activity):
                activities.append(materialized_activity)
        return activities

    data = execute_with_broker(runnable)
    if data:
        return data
    else:
        return []


CACHE_REWIND_SIZE = 1000



