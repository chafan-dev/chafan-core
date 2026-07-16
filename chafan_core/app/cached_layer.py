import datetime
import json
import random
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union


import redis
import requests
import sentry_sdk
import fastapi
from fastapi.encoders import jsonable_encoder
from pydantic import TypeAdapter
from sqlalchemy.orm.session import Session

from chafan_core.app.feed import get_activities_v2, get_random_activities
from chafan_core.app.config import settings
from chafan_core.app import crud, models, schemas
from chafan_core.app.common import is_dev
from chafan_core.app.common import client_ip
from chafan_core.app.user_permission import (
        article_read_allowed,
        question_read_allowed,
        )
from chafan_core.app.data_broker import DataBroker
# TODO 2025-07-20 CachedLayer should not dependent on Materializer
from chafan_core.app.materialize import Materializer
import chafan_core.app.responders as responders
from chafan_core.app.recs.ranking import rank_site_profiles, rank_submissions
from chafan_core.app.recs import matrices as recs_matrices
from chafan_core.app import services
from chafan_core.app.infra import cache as infra_cache
from chafan_core.app.schemas.answer import AnswerPreview
from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.schemas.site import SiteCreate
from chafan_core.utils.base import (
    ContentVisibility,
    EntityType,
    HTTPException_,
    filter_not_none,
    unwrap,
)

import logging
logger = logging.getLogger(__name__)

MatrixType = Dict[int, List[int]]

# User.id -> { User.uuid -> count }
WeightedMatrixType = Dict[int, Dict[str, int]]

# List of { year, contributions }
UserContributions = List[Tuple[int, List[int]]]

MAX_SAMPLED_RELATED_FOLLOWED = 20

T = TypeVar("T")

USER_SITE_PROFILES = "chafan:{user_id}:site-profiles"
ANSWER_CACHE_KEY = "chafan:answer:{uuid}"
ANSWER_FOR_VISITOR_CACHE_KEY = "chafan:answer-for-visitor:{uuid}"
SUBMISSIONS_FOR_USER_CACHE_KEY = "chafan:submissions-for-user:{user_id}"
SITE_SUBMISSIONS_FOR_USER_CACHE_KEY = "chafan:site-submissions:{site_id}:{user_id}"
SITE_INFO_CACHE_KEY = "chafan:site-info:{subdomain}"
SITEMAPS_CACHE_KEY = "chafan:site-maps"
ANSWER_UPVOTES_CACHE_KEY = "chafan:answer-upvotes:{uuid}:{user_id}"
SITE_SUBMISSIONS_CACHE_KEY = "chafan:site-submissions:{site_id}"
VERIFICATION_CODE_CACHE_KEY = "chafan:verification-code:{email}"
SIMILAR_ENTITY_CACHE_KEY = "chafan:similar-entity:{entity_type}"
USER_CONTRIBUTIONS_MAP_CACHE_KEY = "chafan:user-contributions:{user_id}"
FOLLOW_FOLLOW_FANOUT_CACHE_KEY = "chafan:follow-follow-fanout"
NOTIF_FOR_RECEIVER_CACHE_KEY = (
    "chafan:notif-for-receiver:{notification_id}:{receiver_id}"
)
AUTHOR_ANSWERS_FOR_USER_CACHE_KEY = "chafan:user-answers:{author_id}:{user_id}"
USER_FOLLOWERS_CACHE_KEY = "chafan:{user_id}:user-followers:{skip}-{limit}"
USER_FOLLOWED_CACHE_KEY = "chafan:{user_id}:user-followed:{skip}-{limit}"
DAILY_INVITATION_LINK_ID_CACHE_KEY = infra_cache.DAILY_INVITATION_LINK_ID_CACHE_KEY
RELATED_USERS_CACHE_KEY = "chafan:related-users:{user_id}"
REQUEST_TEXT_CACHE_KEY = "chafan:request-text:{url}"

BUMP_VIEW_COUNT_QUEUE_CACHE_KEY = infra_cache.BUMP_VIEW_COUNT_QUEUE_CACHE_KEY

class CachedLayer(object):
    """Transitional façade over RequestContext + responders/materialize.

    Prefer RequestContext for sessions/principal. This class still hosts
    domain helpers until they move to services/.
    """

    def __init__(self, broker: DataBroker, principal_id: Optional[int] = None) -> None:
        # Keep principal on the shared RequestContext (broker is a DataBroker/RequestContext).
        if principal_id is not None:
            broker.principal_id = principal_id
        elif broker.principal_id is not None:
            principal_id = broker.principal_id
        self.broker = broker
        self.principal_id = principal_id
        self.materializer = Materializer(self.broker, self.principal_id)
        self._principal: Optional[models.User] = None
        self._user_contributions_map: Dict[int, UserContributions] = {}
        self._follow_follow_fanout: Optional[WeightedMatrixType] = None
        self._entity_similarity_matrices: Dict[EntityType, MatrixType] = {}

    def bump_view(self, object_type: str, obj_id: int):
        infra_cache.bump_view(object_type, obj_id, self.get_redis())



    def unwrapped_principal_id(self) -> int:
        return unwrap(self.principal_id)

    # Content caching removed (D1 / target architecture Step 3).
    # Redis remains for ephemeral state only (OTP, view-bump queue, daily invitation id).

    def _get_cached_not_none(
        self,
        *,
        key: str,
        typeObj: Any,
        fallable_fetch: Callable[[], Optional[T]],
        hours: int,
    ) -> Optional[T]:
        return fallable_fetch()

    def _get_cached(
        self,
        *,
        key: str,
        typeObj: Any,
        fetch: Callable[[], T],
        hours: int,
        cache_if_dev: bool = False,
    ) -> T:
        # Exception: daily invitation link id is operational state, not content cache.
        if key == DAILY_INVITATION_LINK_ID_CACHE_KEY:
            redis_cli = self.get_redis()
            value = redis_cli.get(key)
            if value is not None:
                return TypeAdapter(typeObj).validate_json(value)
            data = fetch()
            if data is not None:
                redis_cli.set(
                    key,
                    json.dumps(jsonable_encoder(data)),
                    ex=datetime.timedelta(hours=hours),
                )
            return data
        return fetch()

    def _get_cached_non_empty(
        self,
        *,
        key: str,
        typeObj: Any,
        fallable_fetch: Callable[[], List[T]],
        hours: int,
    ) -> List[T]:
        return fallable_fetch()

    def question_schema_from_orm(self, question: models.Question) -> Optional[schemas.Question]:
        logger.info("called cached.layer for question " + str(question))
        return responders.question.question_schema_from_orm(
                self.broker, self.principal_id, question, self)

    def submission_schema_from_orm(self, submission: models.Submission) :
        logger.info("called cached layer for submission to wrap submission " + str(submission.id))
        return responders.submission.submission_schema_from_orm(
                self, submission)

    def article_schema_from_orm(self, article: models.Article):
        logger.info("called cached layer for article")
        return responders.article.article_schema_from_orm(
                self, article, self.principal_id)


    def get_article_by_uuid(self, uuid: str, current_user_id:Optional[int]=None) -> models.Article:
        db = self.get_db()
        article = crud.article.get_by_uuid(db, uuid=uuid)
        if not article_read_allowed(db, article, current_user_id):
            return None
        return article

    def get_article_by_id(self, article_id:int, current_user_id:Optional[int]=None) -> models.Article:
        article = crud.article.get(self.get_db(), id=article_id)
        if not article_read_allowed(self.get_db(), article, current_user_id):
            return None
        return article

    def get_answer_by_id(self, answer_id:int):
        db = self.get_db()
        answer = crud.answer.get_by_id(db, uid=answer_id)
        return answer

    def answer_schema_from_orm(self, answer):
        answer_data = responders.answer.answer_schema_from_orm(self, answer, self.principal_id)
        if answer_data:
            answer_data.upvotes = self.get_answer_upvotes(answer.uuid)
        return answer_data
    def get_answer(self, uuid: str) -> Optional[schemas.Answer]:
        return services.answers.get_answer_schema(self, uuid)

    def get_submissions_for_user(self) -> List[schemas.Submission]:
        return services.submissions.submissions_for_user(self, self.principal_id)

    def invalidate_answer_cache(self, uuid: str) -> None:
        return

    def get_site_by_subdomain(self, subdomain: str):
        return services.sites.get_site_by_subdomain(self.get_db(), subdomain)

    def get_site_info(self, *, subdomain: str) -> Optional[schemas.Site]:
        return services.sites.get_site_info(self, subdomain=subdomain)

    def get_site_submissions_for_user(
        self, *, site: models.Site, user_id: Optional[int], skip: int, limit: int
    ) -> List[schemas.Submission]:
        return services.submissions.site_submissions_for_user(
            self, site=site, user_id=user_id, skip=skip, limit=limit
        )

    def update_site(
        self, *, old_site: models.Site, update_dict: Dict[str, Any]
    ) -> models.Site:
        return services.sites.update_site(
            self.get_db(), old_site=old_site, update_dict=update_dict
        )

    def get_site_maps(self) -> schemas.site.SiteMaps:
        read_db = self.get_db()
        sites = crud.site.get_all(read_db)
        site_maps: Dict[str, schemas.site.SiteMap] = {}
        sites_without_topics: List[schemas.Site] = []
        for s in sites:
            if not s.public_readable:
                continue
            site_data = self.site_schema_from_orm(s)
            if s.category_topic is not None:
                logger.error("site category_topic is deprecated")
            sites_without_topics.append(site_data)
        return schemas.site.SiteMaps(
            site_maps=list(site_maps.values()),
            sites_without_topics=sites_without_topics,
        )

    def create_site(
        self,
        *,
        site_in: SiteCreate,
        moderator: models.User,
        category_topic_id: Optional[int],
    ) -> models.Site:
        return services.sites.create_site(
            self.get_db(),
            site_in=site_in,
            moderator=moderator,
            category_topic_id=category_topic_id,
        )

    def get_redis(self) -> redis.Redis:
        return self.broker.get_redis()

    def invalidate_submission_caches(self, submission: models.Submission) -> None:
        return

    def is_valid_verification_code(self, email: str, code: str) -> bool:
        key = VERIFICATION_CODE_CACHE_KEY.format(email=email)
        value = self.get_redis().get(key)
        if value is None:
            return False
        return value == code

    def get_answer_upvotes(self, uuid: str) -> Optional[schemas.AnswerUpvotes]:
        return services.answers.get_answer_upvotes(
            self.get_db(), uuid=uuid, principal_id=self.principal_id
        )

    def delete_answer(self, uuid: str) -> Optional[str]:
        """Returns error msg"""
        err = services.answers.delete_answer(
            self.get_db(), uuid=uuid, principal_id=self.principal_id
        )
        if err is None:
            self.invalidate_answer_cache(uuid)
        return err

    def invalidate_answer_upvotes_cache(self, uuid: str) -> None:
        return

    def invalidate_comment_caches(self, comment: models.Comment) -> None:
        if comment.answer:
            self.invalidate_answer_cache(comment.answer.uuid)
        elif comment.submission:
            self.invalidate_submission_caches(comment.submission)

    def compute_entity_similarity_matrix(self, entity_type: EntityType) -> MatrixType:
        return recs_matrices.compute_entity_similarity_matrix(self.get_db(), entity_type)

    def get_entity_similarity_matrix(self, entity_type: EntityType) -> MatrixType:
        if entity_type in self._entity_similarity_matrices:
            return self._entity_similarity_matrices[entity_type]
        matrix = self.compute_entity_similarity_matrix(entity_type)
        self._entity_similarity_matrices[entity_type] = matrix
        return matrix

    def compute_follow_follow_fanout(self) -> WeightedMatrixType:
        return recs_matrices.compute_follow_follow_fanout(self.get_db())

    def get_follow_follow_fanout(self) -> WeightedMatrixType:
        if self._follow_follow_fanout:
            return self._follow_follow_fanout
        matrix = self.compute_follow_follow_fanout()
        self._follow_follow_fanout = matrix
        return matrix

    def get_db(self) -> Session:
        return self.broker.get_db()

    def get_current_user(self) -> models.User:
        return unwrap(self.try_get_current_user())

    def try_get_current_user(self) -> Optional[models.User]:
        if self._principal:
            return self._principal
        # Prefer RequestContext principal resolution when broker is a context.
        user = self.broker.try_get_current_user()
        if user is not None:
            self._principal = user
            return user
        if not self.principal_id:
            return None
        self._principal = crud.user.get(self.get_db(), id=self.principal_id)
        return self._principal

    def get_current_active_user(self) -> models.User:
        u = self.get_current_user()
        assert u.is_active
        return u

    def preview_of_user(self, user: models.User) -> schemas.UserPreview:
        return services.people.preview_of_user(self, user)

    def create_audit(self, api: str, request: Optional[fastapi.Request] = None,
                     user_id: Optional[int] = None,
                     request_info: dict = dict()):
        services.audit.create_audit(
            self.get_db(),
            api=api,
            request=request,
            user_id=user_id,
            request_info=request_info,
        )


    def update_notification(
        self,
        notif: models.Notification,
        notif_in: schemas.NotificationUpdate,
    ) -> None:
        crud.notification.update(self.get_db(), db_obj=notif, obj_in=notif_in)

    def notification_schema_from_orm(
        self, notif: models.Notification
    ) -> Optional[schemas.Notification]:
        if self.principal_id is None:
            return None
        return self.materializer.notification_schema_from_orm(notif)

    def get_question_by_id(self, question_id: int):
        question = crud.question.get_by_id(self.get_db(), id=question_id)
        return question

    def get_question_model_http(self, uuid: str) -> models.Question:
        question = crud.question.get_by_uuid(self.get_db(), uuid=uuid)
        if question is None:
            raise HTTPException_(
                status_code=400,
                detail="The question doesn't exist in the system.",
            )
        return question

    def get_question_by_uuid(self, uuid: str, current_user_id:Optional[int]=None) -> Optional[models.Question]:
        question = crud.question.get_by_uuid(self.get_db(), uuid=uuid)
        if question is None:
            return None
        if not question_read_allowed(self, question, current_user_id):
            return None
        return question

    def get_question_subscription(
        self, question: models.Question
    ) -> Optional[schemas.UserQuestionSubscription]:
        current_user = self.try_get_current_user()
        if not current_user:
            return None
        return schemas.UserQuestionSubscription(
            question_uuid=question.uuid,
            subscription_count=question.subscribers.count(),
            subscribed_by_me=(question in current_user.subscribed_questions),
        )

    def get_followers(
        self, user: models.User, skip: int, limit: int
    ) -> List[UserPreview]:
        return services.people.get_followers(self, user, skip, limit)

    def get_followed(
        self, user: models.User, skip: int, limit: int
    ) -> List[UserPreview]:
        return services.people.get_followed(self, user, skip, limit)

    def preview_of_answer(
        self, answer: models.Answer
    ) -> Optional[AnswerPreview]:
        return self.materializer.preview_of_answer(answer)

    def get_authored_answers_for_principal(
        self, author: models.User
    ) -> List[schemas.AnswerPreview]:
        return services.people.get_authored_answers_for_principal(self, author)

    def get_user_follows(self, followed: models.User) -> schemas.UserFollows:
        return services.people.get_user_follows(self, followed)

    def get_daily_invitation_link(self) -> schemas.InvitationLink:
        return services.invitations.get_daily_invitation_link(
            self.get_db(), self.materializer
        )

    def channel_schema_from_orm(self, channel: models.Channel) -> schemas.Channel:
        return self.materializer.channel_schema_from_orm(channel)

    def site_schema_from_orm(self, site: models.Site) -> schemas.Site:
        return responders.site.site_schema_from_orm(self, site)

    def compute_user_contributions_map(self, user: models.User) -> UserContributions:
        return recs_matrices.compute_user_contributions(user)

    def get_user_activity(
            self,
            current_user_id: int,
            before_activity_id: Optional[int],
            limit: int,
            random: bool,
            subject_user_uuid: Optional[str]):
        return services.feed.get_user_activity(
            self,
            current_user_id=current_user_id,
            before_activity_id=before_activity_id,
            limit=limit,
            random=random,
            subject_user_uuid=subject_user_uuid,
        )



    def get_user_contributions(self, user: models.User) -> UserContributions:
        if user.id in self._user_contributions_map:
            return self._user_contributions_map[user.id]
        matrix = self.compute_user_contributions_map(user)
        self._user_contributions_map[user.id] = matrix
        return matrix

    def get_related_user(self, target_user: models.User) -> List[UserPreview]:
        return services.people.get_related_users(self, target_user)

    def get_similar_entity_ids(
        self, id: int, entity_type: EntityType, topK: int = 10
    ) -> List[int]:
        return recs_matrices.similar_entity_ids(
            self.get_db(),
            entity_id=id,
            entity_type=entity_type,
            top_k=topK,
            matrix=self.get_entity_similarity_matrix(entity_type),
        )

    def request_text(self, url: str) -> Optional[str]:
        return services.link_preview.request_text(url)

    def get_site_profiles(self) -> List[schemas.Profile]:
        return services.sites.site_profiles_for_user(
            self.get_db(), self.materializer, self.unwrapped_principal_id()
        )

    def create_site_profile(
        self, *, owner: models.User, site_uuid: str
    ) -> schemas.Profile:
        return services.sites.create_site_profile(
            self.get_db(), self.materializer, owner=owner, site_uuid=site_uuid
        )

    def remove_site_profile(self, *, owner_id: int, site_id: int) -> None:
        services.sites.remove_site_profile(
            self.get_db(), owner_id=owner_id, site_id=site_id
        )

    def try_consume_invitation_link_by_uuid(self, invitation_uuid: str) -> bool:
        return services.invitations.try_consume_invitation_link_by_uuid(
            self.get_db(), invitation_uuid
        )
