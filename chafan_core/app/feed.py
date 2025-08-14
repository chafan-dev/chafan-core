from typing import Dict, List, NamedTuple, Optional, Set, Any
import sentry_sdk
import json
from sqlalchemy.orm import Session

from chafan_core.db.base_class import Base as BaseCrudModel
from chafan_core.app import crud, models, schemas
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.materialize import Materializer
from chafan_core.app.schemas.activity import UserFeedSettings
from chafan_core.app.schemas.event import (
    AnswerQuestionInternal,
    CommentAnswerInternal,
    CommentArticleInternal,
    CommentQuestionInternal,
    CommentSubmissionInternal,
    CreateArticleInternal,
    CreateQuestionInternal,
    CreateSubmissionInternal,
    EventInternal,
    FollowUserInternal,
    ReplyCommentInternal,
    SubscribeArticleColumnInternal,
    UpvoteAnswerInternal,
    UpvoteArticleInternal,
    UpvoteQuestionInternal,
    UpvoteSubmissionInternal,
)
from chafan_core.app.task_utils import execute_with_broker, execute_with_db
from chafan_core.db.session import ReadSessionLocal, SessionLocal
from chafan_core.utils.base import map_, unwrap

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from chafan_core.app.cached_layer import CachedLayer

import logging
logger = logging.getLogger(__name__)


class ActivityDistributionInfo(NamedTuple):
    receiver_ids: Set[int]
    subject_user_uuid: Optional[str]




def lookup_activity_receiver_list(broker: DataBroker, activity: models.Activity)->ActivityDistributionInfo:
    try:
        event = EventInternal.parse_raw(activity.event_json)
    except Exception:
        logger.error("failed to parse Event " + activity.event_json)
        return ActivityDistributionInfo(receiver_ids=set(), subject_user_uuid=None)
    # TODO We need to consider different types of events 2025-07-20
    logger.info(f"get event: {event}")
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

def new_activity_into_feed(broker: DataBroker, activity:models.Activity) -> None:
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
            write_db.commit()



# TODO This is the v1 api. To be removed. 2025-07-19
def get_activity_dist_info(
    read_db: Session, activity: models.Activity
) -> ActivityDistributionInfo:
    receivers: Dict[int, models.User] = {}
    subject_user_uuid = None
    try:
        event = EventInternal.parse_raw(activity.event_json)
    except Exception:
        sentry_sdk.capture_message(
            f"Failed to materialize event: {activity.event_json}",
        )
        return ActivityDistributionInfo(receiver_ids=set(), subject_user_uuid=None)

    if hasattr(event.content, "subject_id"):
        subject = crud.user.get(read_db, id=event.content.subject_id)
        assert subject is not None
        subject_user_uuid = subject.uuid
        for follower in subject.followers:
            receivers[follower.id] = follower
    if isinstance(event.content, CreateQuestionInternal):
        question = crud.question.get(read_db, id=event.content.question_id)
        assert question is not None
        for profile in question.site.profiles:
            if profile.owner_id != event.content.subject_id:
                receivers[profile.owner_id] = profile.owner
    elif isinstance(event.content, CreateSubmissionInternal):
        pass
    elif isinstance(event.content, UpvoteSubmissionInternal):
        pass
    elif isinstance(event.content, CommentSubmissionInternal):
        pass
    elif isinstance(event.content, CreateArticleInternal):
        article = crud.article.get(read_db, id=event.content.article_id)
        assert article is not None
        for user in article.article_column.subscribers:
            if user.id != event.content.subject_id:
                receivers[user.id] = user
    elif isinstance(event.content, AnswerQuestionInternal):
        answer = crud.answer.get(read_db, id=event.content.answer_id)
        assert answer is not None
        for user in answer.question.subscribers:
            if user.id != event.content.subject_id:
                receivers[user.id] = user
    elif isinstance(event.content, UpvoteAnswerInternal):
        answer = crud.answer.get(read_db, id=event.content.answer_id)
        assert answer is not None
        for answer_upvote in read_db.query(models.Answer_Upvotes).filter_by(
            answer_id=answer.id
        ):
            if answer_upvote.voter_id in receivers:
                del receivers[answer_upvote.voter_id]
        if answer.author_id in receivers:
            del receivers[answer.author_id]
    elif isinstance(event.content, UpvoteQuestionInternal):
        question = crud.question.get(read_db, id=event.content.question_id)
        assert question is not None
        for question_upvote in read_db.query(models.QuestionUpvotes).filter_by(
            question_id=question.id
        ):
            if question_upvote.voter_id in receivers:
                del receivers[question_upvote.voter_id]
        if question.author_id in receivers:
            del receivers[question.author_id]
    elif isinstance(event.content, UpvoteArticleInternal):
        article = crud.article.get(read_db, id=event.content.article_id)
        assert article is not None
        for article_upvote in read_db.query(models.ArticleUpvotes).filter_by(
            article_id=article.id
        ):
            if article_upvote.voter_id in receivers:
                del receivers[article_upvote.voter_id]
        if article.author_id in receivers:
            del receivers[article.author_id]
    elif isinstance(event.content, SubscribeArticleColumnInternal):
        article_column = crud.article_column.get(
            read_db, id=event.content.article_column_id
        )
        assert article_column is not None
        for user in article_column.subscribers:
            if user.id in receivers:
                del receivers[user.id]
        if article_column.owner_id in receivers:
            del receivers[article_column.owner_id]
    elif isinstance(event.content, CommentQuestionInternal):
        pass
    elif isinstance(event.content, CommentAnswerInternal):
        pass
    elif isinstance(event.content, CommentArticleInternal):
        pass
    elif isinstance(event.content, ReplyCommentInternal):
        pass
    elif isinstance(event.content, FollowUserInternal):
        if event.content.user_id in receivers:
            del receivers[event.content.user_id]
        removed_receiver_ids = []
        for receiver in receivers.values():
            if receiver.followed.filter_by(id=event.content.user_id).first():  # type: ignore
                removed_receiver_ids.append(receiver.id)
        for i in removed_receiver_ids:
            del receivers[i]
    else:
        sentry_sdk.capture_message(f"Unknown event: {event}")
        return ActivityDistributionInfo(receiver_ids=set(), subject_user_uuid=None)
    return ActivityDistributionInfo(
        receiver_ids=set(receivers.keys()), subject_user_uuid=subject_user_uuid
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
    data_broker: DataBroker,
    activity: models.Activity,
    receiver_id: int,
    feed_settings: Optional[UserFeedSettings],
) -> Optional[schemas.Activity]:
    materializer = Materializer(data_broker, receiver_id)
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
def retrieve_content(event: EventInternal, cached_layer) -> Optional[BaseCrudModel]:
    assert isinstance(event, EventInternal)
    c = event.content
    if isinstance(c, CreateQuestionInternal):
        question = cached_layer.get_question_by_id(c.question_id)
        if question.is_hidden:
            logger.warning("Skip a hidden question: " + str(question))
            return None
        return question
    if isinstance(c, AnswerQuestionInternal):
        answer = cached_layer.get_answer_by_id(c.answer_id)
        if (answer.is_hidden_by_moderator) or \
            (not answer.is_published):
            logger.warning("Skip a hidden answer: " + str(answer))
            return None
        return answer
    if isinstance(c, CreateArticleInternal):
        art = cached_layer.get_article_by_id(c.article_id)
        return art

    logger.error(f"Not supported event type: {event}")
    return None #TODO throw exception

async def get_content_from_eventjson(
        cached_layer: "CachedLayer",
        event_json: str) -> Optional[BaseCrudModel]:
    event = EventInternal.parse_raw(event_json)
    content = retrieve_content(event, cached_layer)
    return content

async def get_site_activities(
    cached_layer: "CachedLayer",
    site,
    limit: int,
    all_sites = False) -> List[BaseCrudModel]:
    db = cached_layer.get_db()
    if (site is None) and (not all_sites):
        raise ValueError("site not found ")
    if (not all_sites) and (not site.public_readable):
        raise ValueError("site not allowed ")
    feeds = db.query(models.Activity)
    if not all_sites:
        feeds = feeds.filter_by(site_id=site.id)
    feeds = feeds.order_by(models.Activity.id.desc()).limit(limit)
    activities = []
    for feed in feeds:
        obj = await get_content_from_eventjson(cached_layer, feed.event_json)
        if obj is not None:
            assert isinstance(obj, BaseCrudModel)
            activities.append(obj)
    return activities

async def get_activities_v2(
    *,
    cached_layer: "CachedLayer",
    before_activity_id: Optional[int],
    limit: int,
    receiver_user_id: int,
    subject_user_uuid: Optional[str],
) -> List[schemas.Activity]:
    db = cached_layer.get_db()
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
            cached_layer.broker, feed.activity, receiver_user_id, feed_settings
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
    def runnable(broker: DataBroker) -> List[schemas.Activity]:
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


ALWAYS_PUBLIC_EVENT_VERBS = set(
    ["create_article", "comment_article", "upvote_article", "follow_article_column"]
)


def _is_public_activity(activity: schemas.Activity) -> bool:
    if activity.site and activity.site.public_readable:
        return True
    return activity.event.content.verb in ALWAYS_PUBLIC_EVENT_VERBS


def get_random_activities(
    *, receiver_user_id: int, before_activity_id: Optional[int], limit: int
) -> List[schemas.Activity]:
    id_bucket = receiver_user_id % 10

    def runnable(broker: DataBroker) -> List[schemas.Activity]:
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



