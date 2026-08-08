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

# --------------------------------------------------------------------------
# The two timelines.
#
# They were always two questions -- "what was delivered to me" and "what did
# this user do" -- and they used to share one query against Feed. That is why
# the subject branch ignored receiver_id entirely and asked the delivery table
# a question about authorship. See
# docs/proposals/2026-08-04-activity-feed-reassignment.md.
#
# Both still materialize per viewer, so a row in either table grants nothing:
# the responder permission check runs per item at read time and an item the
# viewer may not see silently does not render.
# --------------------------------------------------------------------------

# TODO: honor the receiver's feed_settings.blocked_origins. `is_blocked` above
# and the two /activities/settings endpoints are all still live, so a user can
# mute a site, see the setting persist, and keep seeing that site. Restoring it
# is three lines -- parse feed_settings into a UserFeedSettings and pass it
# here instead of None. Production has zero users holding a mute (checked
# 2026-08-06), so deleting the feature is at least as likely as restoring it;
# either way it should be a decision rather than this silence.
NO_FEED_SETTINGS: Optional[UserFeedSettings] = None


def receiver_feed(
    ctx: "RequestContext",
    *,
    receiver_id: int,
    before_activity_id: Optional[int],
    limit: int,
) -> List[schemas.Activity]:
    """What was delivered to this user, newest first.

    No deduplication and no over-fetch. ``Feed`` carries
    ``UNIQUE (activity_id, receiver_id)``, so filtering by a single receiver
    returns at most one row per activity. The ``limit * 2`` and the seen-set
    this replaces existed only because the subject timeline ran through here
    too, querying across *all* receivers -- that is where one activity came
    back once per follower.
    """
    db = ctx.get_db()
    feeds = db.query(models.Feed).filter_by(receiver_id=receiver_id)
    if before_activity_id:
        feeds = feeds.filter(models.Feed.activity_id < before_activity_id)
    feeds = feeds.order_by(models.Feed.activity_id.desc()).limit(limit)
    activities = []
    for feed in feeds:
        activity = materialize_activity(
            ctx, feed.activity, receiver_id, NO_FEED_SETTINGS
        )
        if activity is not None:
            activities.append(activity)
    return activities


def subject_timeline(
    ctx: "RequestContext",
    *,
    subject_user_uuid: str,
    viewer_id: int,
    before_activity_id: Optional[int],
    limit: int,
) -> List[schemas.Activity]:
    """Everything one user did, newest first, as seen by ``viewer_id``.

    Reads the event log rather than the delivery table, so it no longer depends
    on the subject having an audience: a user with no followers and no column
    subscribers has a complete profile here instead of a blank one.

    The uuid is resolved to an id because ``Activity.subject_user_id`` is an
    integer FK while the API parameter is the public uuid. A uuid naming nobody
    yields an **empty timeline rather than an error** -- that is a reader asking
    about somebody who is gone, not a malformed request.

    A page can come back shorter than ``limit`` when the viewer cannot read some
    of the subject's sites, because the gate runs per item after the fetch.
    Accepted deliberately: filling the page would mean looping until enough
    items survive, which is complexity bought against a load this deployment
    does not have.
    """
    db = ctx.get_db()
    subject = crud.user.get_by_uuid(db, uuid=subject_user_uuid)
    if subject is None:
        return []
    query = db.query(models.Activity).filter(
        models.Activity.subject_user_id == subject.id
    )
    if before_activity_id:
        query = query.filter(models.Activity.id < before_activity_id)
    query = query.order_by(models.Activity.id.desc()).limit(limit)
    activities = []
    for activity in query:
        materialized = materialize_activity(ctx, activity, viewer_id, NO_FEED_SETTINGS)
        if materialized is not None:
            activities.append(materialized)
    return activities
