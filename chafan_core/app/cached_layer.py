import datetime
import json
import random
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union


import redis
import requests
import sentry_sdk
from fastapi.encoders import jsonable_encoder
from pydantic import TypeAdapter
from sqlalchemy.orm.session import Session

from chafan_core.app.feed import get_activities_v2, get_random_activities
from chafan_core.app.config import settings
from chafan_core.app import crud, models, schemas
from chafan_core.app.common import is_dev
from chafan_core.app.data_broker import DataBroker
# TODO 2025-07-20 CachedLayer should not dependent on Materializer
from chafan_core.app.materialize import Materializer
import chafan_core.app.responders as responders
from chafan_core.app.recs.ranking import rank_site_profiles, rank_submissions
from chafan_core.app.schemas.answer import AnswerPreview, AnswerPreviewForVisitor
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
DAILY_INVITATION_LINK_ID_CACHE_KEY = "chafan:daily-invitation-link-id"
RELATED_USERS_CACHE_KEY = "chafan:related-users:{user_id}"
REQUEST_TEXT_CACHE_KEY = "chafan:request-text:{url}"

BUMP_VIEW_COUNT_QUEUE_CACHE_KEY = "chafan:bump-view-count"

class CachedLayer(object):
    def __init__(self, broker: DataBroker, principal_id: Optional[int] = None) -> None:
        self.broker = broker
        self.principal_id = principal_id
        self.materializer = Materializer(self.broker, self.principal_id)
        self._principal: Optional[models.User] = None
        self._user_contributions_map: Dict[int, UserContributions] = {}
        self._follow_follow_fanout: Optional[WeightedMatrixType] = None
        self._entity_similarity_matrices: Dict[EntityType, MatrixType] = {}

    def bump_view(self, object_type: str, obj_id:int):
        obj_str = f"{object_type}:{obj_id}"
        self.get_redis().rpush(BUMP_VIEW_COUNT_QUEUE_CACHE_KEY, obj_str)



    def unwrapped_principal_id(self) -> int:
        return unwrap(self.principal_id)

    def _get_cached_not_none(
        self,
        *,
        key: str,
        typeObj: Any,
        fallable_fetch: Callable[[], Optional[T]],
        hours: int,
    ) -> Optional[T]:
        redis_cli = self.get_redis()
        value = redis_cli.get(key)
        if value is not None:
            TypeAdapter(typeObj).validate_json(value)
        data = fallable_fetch()
        if data and not is_dev():
            redis_cli.set(
                key,
                json.dumps(jsonable_encoder(data)),
                ex=datetime.timedelta(hours=hours),
            )
        return data

    def _get_cached(
        self,
        *,
        key: str,
        typeObj: Any,
        fetch: Callable[[], T],
        hours: int,
        cache_if_dev: bool = False,
    ) -> T:
        redis_cli = self.get_redis()
        value = redis_cli.get(key)
        if value is not None:
            return TypeAdapter(typeObj).validate_json(value)
        data = fetch()
        if data and (not is_dev() or cache_if_dev):
            redis_cli.set(
                key,
                json.dumps(jsonable_encoder(data)),
                ex=datetime.timedelta(hours=hours),
            )
        return data

    def _get_cached_non_empty(
        self,
        *,
        key: str,
        typeObj: Any,
        fallable_fetch: Callable[[], List[T]],
        hours: int,
    ) -> List[T]:
        redis_cli = self.get_redis()
        value = redis_cli.get(key)
        if value is not None:
            return TypeAdapter(typeObj).validate_json(value)
        data = fallable_fetch()
        if data and not is_dev():
            redis_cli.set(
                key,
                json.dumps(jsonable_encoder(data)),
                ex=datetime.timedelta(hours=hours),
            )
        return data

    def question_schema_from_orm(self, question: models.Question) -> Optional[schemas.Question]:
        logger.info("called cached.layer for question " + str(question))
        return responders.question.question_schema_from_orm(
                self.broker, self.principal_id, question, self)

    def submission_schema_from_orm(self, submission: models.Submission) :
        logger.info("called cached layer for submission")
        return responders.submission.submission_schema_from_orm(
                self, submission)

    def article_schema_from_orm(self, article: models.Article):
        logger.info("called cached layer for article")
        return responders.article.article_schema_from_orm(
                self, article, self.principal_id)


    def get_article_by_id(self, article_id:int):
        logger.info(f"get_article cached layer id={article_id}")
        # TODO not done
        return None

    def get_answer_by_id(self, answer_id:int):
        db = self.get_db()
        answer = crud.answer.get_by_id(db, uid=answer_id)
        return answer

    def answer_schema_from_orm(self, answer):
        answer_data = responders.answer.answer_schema_from_orm(self, answer, self.principal_id)
        if answer_data:
            answer_data.upvotes = self.get_answer_upvotes(answer.uuid)
        return answer_data
    def get_answer(
        self, uuid: str
    ) -> Optional[Union[schemas.Answer, schemas.AnswerForVisitor]]:
        db = self.get_db()
        answer = crud.answer.get_by_uuid(db, uuid=uuid)
        if answer is None:
            return None
        answer_data = responders.answer.answer_schema_from_orm(self, answer, self.principal_id)
        if answer_data:
            answer_data.upvotes = self.get_answer_upvotes(uuid)
        return answer_data

    def get_submissions_for_user(
        self,
    ) -> Union[List[schemas.Submission], List[schemas.SubmissionForVisitor]]:
        return self._get_submissions_for_user(self.principal_id)
        # def f() -> Union[List[schemas.Submission], List[schemas.SubmissionForVisitor]]:
        #     return self._get_submissions_for_user(self.principal_id)
        #
        # return self._get_cached(
        #     key=SUBMISSIONS_FOR_USER_CACHE_KEY.format(user_id=self.principal_id),
        #     typeObj=Union[List[schemas.Submission], List[schemas.SubmissionForVisitor]],
        #     fetch=f,
        #     hours=24,
        # )

    def invalidate_answer_cache(self, uuid: str) -> None:
        redis_cli = self.get_redis()
        redis_cli.delete(ANSWER_CACHE_KEY.format(uuid=uuid))
        redis_cli.delete(ANSWER_FOR_VISITOR_CACHE_KEY.format(uuid=uuid))

    def _get_cached_recent_k_submissions_of_site(
        self, site: models.Site, k: int
    ) -> List[schemas.Submission]:
        redis = self.broker.get_redis()
        key = f"chafan:cached-recent-k-submissions-of-site:{site.id}:{k}"
        value = redis.get(key)
        if value is not None:
            return TypeAdapter(List[schemas.Submission]).validate_json(value)
        data = filter_not_none(
            [self.materializer.submission_schema_from_orm(s) for s in site.submissions]
        )[:k]
        if not is_dev():
            redis.set(
                key, json.dumps(jsonable_encoder(data)), ex=datetime.timedelta(hours=24)
            )
        return data

    def _get_submissions_for_user(
        self, current_user_id: Optional[int]
    ) -> Union[List[schemas.Submission], List[schemas.SubmissionForVisitor]]:
        if current_user_id:
            current_user = crud.user.get(self.broker.get_db(), id=current_user_id)
            assert current_user is not None
            submissions = []
            for profile in current_user.profiles:
                submissions.extend(
                    self._get_cached_recent_k_submissions_of_site(profile.site, k=20)
                )
            if len(submissions) == 0:
                for site in crud.site.get_all_public_readable(self.broker.get_db()):
                    submissions.extend(
                        filter_not_none(
                            [
                                self.materializer.submission_schema_from_orm(s)
                                for s in site.submissions
                            ]
                        )[:5]
                    )
            return rank_submissions(submissions)
        else:
            submissions_for_visitors: List[schemas.SubmissionForVisitor] = []
            for site in crud.site.get_all_public_readable(self.broker.get_db()):
                submissions_for_visitors.extend(
                    filter_not_none(
                        [
                            self.materializer.submission_for_visitor_schema_from_orm(s)
                            for s in site.submissions
                        ]
                    )[:10]
                )
            print(submissions_for_visitors)
            return rank_submissions(submissions_for_visitors)

    def get_answer_for_visitor(self, uuid: str) -> Optional[schemas.AnswerForVisitor]:
        redis_cli = self.get_redis()
        key = ANSWER_FOR_VISITOR_CACHE_KEY.format(uuid=uuid)
        value = redis_cli.get(key)
        if value is not None:
            return schemas.AnswerForVisitor.model_validate_json(value)
        db = self.get_db()
        answer = crud.answer.get_by_uuid(db, uuid=uuid)
        if answer is None:
            return None
        if answer.visibility != ContentVisibility.ANYONE:
            return None
        answer_data = self.materializer.answer_for_visitor_schema_from_orm(answer)
        if answer_data is None:
            return None
        if not is_dev():
            redis_cli.set(key, answer_data.json(), ex=datetime.timedelta(hours=12))
        return answer_data

    def get_site_by_subdomain(self, subdomain: str):
        return crud.site.get_by_subdomain(self.get_db(), subdomain=subdomain)

    def get_site_info(self, *, subdomain: str) -> Optional[schemas.Site]:
        redis_cli = self.get_redis()
        key = SITE_INFO_CACHE_KEY.format(subdomain=subdomain)
        value = redis_cli.get(key)
        if value is not None:
            return schemas.Site.model_validate_json(value)
        site = crud.site.get_by_subdomain(self.get_db(), subdomain=subdomain)
        if site is None:
            return None
        site_data = self.site_schema_from_orm(site)
        if not is_dev():
            redis_cli.set(key, site_data.json(), ex=datetime.timedelta(hours=24))
        return site_data

    def get_site_submissions_for_user(
        self, *, site: models.Site, user_id: Optional[int], skip: int, limit: int
    ) -> Union[List[schemas.Submission], List[schemas.SubmissionForVisitor]]:
        redis = self.get_redis()
        key = SITE_SUBMISSIONS_FOR_USER_CACHE_KEY.format(
            site_id=site.id, user_id=user_id
        )
        value = redis.get(key)
        if value is not None:
            if user_id:
                return TypeAdapter(List[schemas.Submission]).validate_json(value)[
                    skip : skip + limit
                ]
            else:
                return TypeAdapter(List[schemas.SubmissionForVisitor]).validate_json(
                    value
                )[skip : skip + limit]
        submissions: List[Any] = []
        if user_id:
            # FIXME: compute rank async
            submissions = rank_submissions(
                filter_not_none(
                    [
                        self.materializer.submission_schema_from_orm(submission)
                        for submission in site.submissions
                    ]
                )
            )
        else:
            # FIXME: compute rank async
            logger.error("TODO submission list for visitors are turned off due to `desc` missing") #2025-Jul-30
            submissions = []
            # submissions = rank_submissions(
            #     filter_not_none(
            #         [
            #             self.materializer.submission_for_visitor_schema_from_orm(
            #                 submission
            #             )
            #             for submission in site.submissions[:10]
            #         ]
            #     )
            # )
        if False and not is_dev():
            redis.set(
                key,
                json.dumps(jsonable_encoder(submissions)),
                ex=datetime.timedelta(hours=1),
            )
        return submissions[skip : skip + limit]

    def update_site(
        self, *, old_site: models.Site, update_dict: Dict[str, Any]
    ) -> models.Site:
        site = crud.site.update(self.get_db(), db_obj=old_site, obj_in=update_dict)
        self.get_redis().delete(SITEMAPS_CACHE_KEY)
        self.get_redis().delete(SITE_INFO_CACHE_KEY.format(subdomain=site.subdomain))
        return site

    def get_site_maps(self) -> schemas.site.SiteMaps:
        redis_cli = self.get_redis()
        value = redis_cli.get(SITEMAPS_CACHE_KEY)
        if value is not None:
            return schemas.site.SiteMaps.model_validate_json(value)
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
        data = schemas.site.SiteMaps(
            site_maps=list(site_maps.values()),
            sites_without_topics=sites_without_topics,
        )
        redis_cli.set(
            SITEMAPS_CACHE_KEY, data.json(), ex=settings.CACHE_SITEMAP_VALID_HOURS)
        return data

    def create_site(
        self,
        *,
        site_in: SiteCreate,
        moderator: models.User,
        category_topic_id: Optional[int],
    ) -> models.Site:
        site = crud.site.create_with_permission_type(
            self.get_db(),
            obj_in=site_in,
            moderator=moderator,
            category_topic_id=category_topic_id,
        )
        self.get_redis().delete(SITEMAPS_CACHE_KEY)
        return site

    def get_redis(self) -> redis.Redis:
        return self.broker.get_redis()

    def invalidate_submission_caches(self, submission: models.Submission) -> None:
        redis_cli = self.get_redis()
        redis_cli.delete(
            SUBMISSIONS_FOR_USER_CACHE_KEY.format(user_id=submission.author_id)
        )
        redis_cli.delete(SITE_SUBMISSIONS_CACHE_KEY.format(site_id=submission.site_id))
        for k in redis_cli.scan_iter(
            SITE_SUBMISSIONS_FOR_USER_CACHE_KEY.format(
                site_id=submission.site_id, user_id="*"
            )
        ):
            redis_cli.delete(k)

    def is_valid_verification_code(self, email: str, code: str) -> bool:
        key = VERIFICATION_CODE_CACHE_KEY.format(email=email)
        value = self.get_redis().get(key)
        if value is None:
            return False
        return value == code

    def get_answer_upvotes(self, uuid: str) -> Optional[schemas.AnswerUpvotes]:
        redis_cli = self.get_redis()
        key = ANSWER_UPVOTES_CACHE_KEY.format(uuid=uuid, user_id=self.principal_id)
        value = redis_cli.get(key)
        if value is not None:
            return schemas.AnswerUpvotes.model_validate_json(value)
        db = self.get_db()
        answer = crud.answer.get_by_uuid(db, uuid=uuid)
        if answer is None:
            return None
        upvoted = False
        if self.principal_id:
            upvoted = (
                db.query(models.Answer_Upvotes)
                .filter_by(
                    answer_id=answer.id, voter_id=self.principal_id, cancelled=False
                )
                .first()
                is not None
            )
        valid_upvotes = (
            db.query(models.Answer_Upvotes)
            .filter_by(answer_id=answer.id, cancelled=False)
            .count()
        )
        data = schemas.AnswerUpvotes(
            answer_uuid=answer.uuid, count=valid_upvotes, upvoted=upvoted
        )
        if not is_dev():
            redis_cli.set(key, data.json(), ex=datetime.timedelta(hours=6))
        return data

    def delete_answer(self, uuid: str) -> Optional[str]:
        """Returns error msg"""
        db = self.get_db()
        answer = crud.answer.get_by_uuid(db, uuid=uuid)
        if answer is None:
            return "The answer doesn't exists in the system."
        if answer.author_id != self.principal_id:
            return "Unauthorized."
        crud.answer.delete_forever(db, answer=answer)
        self.invalidate_answer_cache(uuid)
        return None

    def invalidate_answer_upvotes_cache(self, uuid: str) -> None:
        self.get_redis().delete(
            ANSWER_UPVOTES_CACHE_KEY.format(uuid=uuid, user_id=self.principal_id)
        )

    def invalidate_comment_caches(self, comment: models.Comment) -> None:
        if comment.answer:
            self.invalidate_answer_cache(comment.answer.uuid)
        elif comment.submission:
            self.invalidate_submission_caches(comment.submission)

    def compute_entity_similarity_matrix(self, entity_type: EntityType) -> MatrixType:
        entities: List[Tuple[int, Set[str]]] = []
        if entity_type == EntityType.sites:
            for site in crud.site.get_all(self.get_db()):
                if site.keywords:
                    entities.append((site.id, set(site.keywords)))
        elif entity_type == EntityType.users:
            for user in crud.user.get_all_active_users(self.get_db()):
                if user.keywords:
                    entities.append((user.id, set(user.keywords)))
        else:
            raise Exception(f"Unknown entity type: {entity_type}")

        matrix: MatrixType = {}
        for query_id, query_keywords in entities:
            candidates = []
            for candidate_id, candidate_keywords in entities:
                if candidate_id == query_id:
                    continue
                candidates.append(
                    (candidate_id, len(candidate_keywords.intersection(query_keywords)))
                )
            candidates.sort(key=lambda p: p[1], reverse=True)
            matrix[query_id] = [query_id for query_id, _ in candidates[:50]]
        return matrix

    def get_entity_similarity_matrix(self, entity_type: EntityType) -> MatrixType:
        if entity_type in self._entity_similarity_matrices:
            return self._entity_similarity_matrices[entity_type]

        def f() -> MatrixType:
            return self.compute_entity_similarity_matrix(entity_type)

        matrix = self._get_cached(
            key=SIMILAR_ENTITY_CACHE_KEY.format(entity_type=entity_type),
            typeObj=MatrixType,
            fetch=f,
            hours=24,
        )
        self._entity_similarity_matrices[entity_type] = matrix
        return matrix

    def compute_follow_follow_fanout(self) -> WeightedMatrixType:
        matrix: WeightedMatrixType = {}
        for user in crud.user.get_all_active_users(self.get_db()):
            user_ids: Counter = Counter()
            for followed in user.followed:
                for followed_followed in followed.followed:
                    if followed_followed.id != user.id:
                        user_ids[followed_followed.uuid] += 1
            matrix[user.id] = dict(user_ids)
        return matrix

    def get_follow_follow_fanout(self) -> WeightedMatrixType:
        if self._follow_follow_fanout:
            return self._follow_follow_fanout
        matrix = self._get_cached(
            key=FOLLOW_FOLLOW_FANOUT_CACHE_KEY,
            typeObj=WeightedMatrixType,
            fetch=self.compute_follow_follow_fanout,
            hours=12,
        )
        self._follow_follow_fanout = matrix
        return matrix

    def get_db(self) -> Session:
        return self.broker.get_db()

    def get_current_user(self) -> models.User:
        return unwrap(self.try_get_current_user())

    def try_get_current_user(self) -> Optional[models.User]:
        if self._principal:
            return self._principal
        if not self.principal_id:
            return None
        self._principal = crud.user.get(self.get_db(), id=self.principal_id)
        return self._principal

    def get_current_active_user(self) -> models.User:
        u = self.get_current_user()
        assert u.is_active
        return u

    def preview_of_user(self, user: models.User) -> schemas.UserPreview:
        user_preview = self.materializer.preview_of_user(user)
        # Annotate social anontations
        principal_id = self.principal_id
        if principal_id:
            m = self.get_follow_follow_fanout()
            if principal_id in m and user_preview.uuid in m[principal_id]:
                user_preview.social_annotations.follow_follows = m[principal_id][
                    user_preview.uuid
                ]
            else:
                user_preview.social_annotations.follow_follows = 0
        user_preview.follows = self.get_user_follows(user)
        return user_preview

    def update_notification(
        self,
        notif: models.Notification,
        notif_in: schemas.NotificationUpdate,
    ) -> None:
        notif = crud.notification.update(self.get_db(), db_obj=notif, obj_in=notif_in)
        self.get_redis().delete(
            NOTIF_FOR_RECEIVER_CACHE_KEY.format(
                notification_id=notif.id,
                receiver_id=notif.receiver_id,
            )
        )

    def notification_schema_from_orm(
        self, notif: models.Notification
    ) -> Optional[schemas.Notification]:
        if self.principal_id is None:
            return None
        key = NOTIF_FOR_RECEIVER_CACHE_KEY.format(
            notification_id=notif.id, receiver_id=self.principal_id
        )
        redis_cli = self.get_redis()
        value = redis_cli.get(key)
        if value is not None:
            return schemas.Notification.model_validate_json(value)
        data = self.materializer.notification_schema_from_orm(notif)
        if data and not is_dev():
            redis_cli.set(key, data.json(), ex=datetime.timedelta(hours=24))
        return data

    def get_question_by_id(self, question_id: int):
        question = crud.question.get_by_id(self.get_db(), id=question_id)
        return question

    def get_question_model_http(self, uuid: str) -> models.Question:
        question = crud.question.get_by_uuid(self.get_db(), uuid=uuid)
        if question is None:
            raise HTTPException_(
                status_code=400,
                detail="The question doesn't exists in the system.",
            )
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
        def f() -> List[UserPreview]:
            return [
                self.preview_of_user(u) for u in user.followers[skip : skip + limit]
            ]

        return self._get_cached(
            key=USER_FOLLOWERS_CACHE_KEY.format(
                user_id=user.id, skip=skip, limit=limit
            ),
            typeObj=List[UserPreview],
            fetch=f,
            hours=12,
        )

    def get_followed(
        self, user: models.User, skip: int, limit: int
    ) -> List[UserPreview]:
        def f() -> List[UserPreview]:
            return [self.preview_of_user(u) for u in user.followed[skip : skip + limit]]

        return self._get_cached(
            key=USER_FOLLOWED_CACHE_KEY.format(user_id=user.id, skip=skip, limit=limit),
            typeObj=List[UserPreview],
            fetch=f,
            hours=12,
        )

    def preview_of_answer(
        self, answer: models.Answer
    ) -> Union[Optional[AnswerPreview], Optional[AnswerPreviewForVisitor]]:
        if self.principal_id:
            return self.materializer.preview_of_answer(answer)
        else:
            return self.materializer.preview_of_answer_for_visitor(answer)

    def get_authored_answers_for_principal(
        self, author: models.User
    ) -> Union[List[schemas.AnswerPreview], List[schemas.AnswerPreviewForVisitor]]:
        key = AUTHOR_ANSWERS_FOR_USER_CACHE_KEY.format(
            author_id=author.id, user_id=self.principal_id
        )

        def f() -> (
            Union[List[schemas.AnswerPreview], List[schemas.AnswerPreviewForVisitor]]
        ):
            if self.principal_id:
                return filter_not_none(
                    [
                        self.materializer.preview_of_answer(answer)
                        for answer in author.answers
                    ]
                )
            else:
                return filter_not_none(
                    [
                        self.materializer.preview_of_answer_for_visitor(answer)
                        for answer in author.answers
                    ]
                )

        return self._get_cached_non_empty(
            key=key,
            typeObj=Union[
                List[schemas.AnswerPreview], List[schemas.AnswerPreviewForVisitor]
            ],
            fallable_fetch=f,
            hours=24,
        )  # type: ignore

    def get_user_follows(self, followed: models.User) -> schemas.UserFollows:
        current_user = self.try_get_current_user()
        if current_user:
            followed_by_me = followed in current_user.followed
        else:
            followed_by_me = False
        return schemas.UserFollows(
            user_uuid=followed.uuid,
            followers_count=followed.followers.count(),
            followed_count=followed.followed.count(),  # type: ignore
            followed_by_me=followed_by_me,
        )

    def get_daily_invitation_link(self) -> schemas.InvitationLink:
        db = self.get_db()

        def f() -> int:
            return crud.invitation_link.create_invitation(
                db, invited_to_site_id=None, inviter=crud.user.get_superuser(db)
            ).id

        cached_id = self._get_cached(
            key=DAILY_INVITATION_LINK_ID_CACHE_KEY,
            typeObj=int,
            fetch=f,
            hours=24,
            cache_if_dev=True,
        )
        return self.materializer.invitation_link_schema_from_orm(
            unwrap(crud.invitation_link.get(db, id=cached_id))
        )

    def channel_schema_from_orm(self, channel: models.Channel) -> schemas.Channel:
        return self.materializer.channel_schema_from_orm(channel)

    def site_schema_from_orm(self, site: models.Site) -> schemas.Site:
        return responders.site.site_schema_from_orm(self, site)

    def compute_user_contributions_map(self, user: models.User) -> UserContributions:
        d: Dict[int, Dict[int, Dict[str, int]]] = {}

        def incr(timestamp: datetime.datetime, action: str) -> None:
            year = timestamp.year
            day = min(timestamp.timetuple().tm_yday, 364)
            if year not in d:
                d[year] = {}
            if day not in d[year]:
                d[year][day] = {}
            if action not in d[year][day]:
                d[year][day][action] = 0
            d[year][day][action] += 1

        for answer in user.answers:
            incr(answer.updated_at, "answer")
        for article in user.articles:
            incr(article.created_at, "article")
        for question in user.questions:
            incr(question.created_at, "question")
        for submission in user.submissions:
            incr(submission.created_at, "submission")
        ret: UserContributions = []
        if not d:
            return ret
        for year in reversed(range(min(d.keys()), max(d.keys()) + 1)):
            day_contribs = []
            for day in range(1, 365):
                if year not in d or day not in d[year]:
                    day_contribs.append(0)
                else:
                    v = 0
                    if "answer" in d[year][day]:
                        v += max(d[year][day]["answer"], 2)
                    if "question" in d[year][day]:
                        v += max(d[year][day]["question"], 1)
                    if "submission" in d[year][day]:
                        v += max(int(float(d[year][day]["submission"]) / 2.0), 1)
                    if "article" in d[year][day]:
                        v += max(d[year][day]["article"], 2)
                    day_contribs.append(min(int(v), 3))
            ret.append((year, day_contribs))
        return ret

    async def get_user_activity(
            self,
            current_user_id: int,
            before_activity_id:Optional[int],
            limit:int,
            random:bool,
            subject_user_uuid: Optional[str]):
        logger.info(f"cached_layer get_user_activity for {current_user_id}")
        redis = self.get_redis()
        key = f"chafan:feed-cache:user:{current_user_id}:before_activity_id={before_activity_id}&limit={limit}&subject_user_uuid={subject_user_uuid}"
        value = redis.get(key)
        value = None
        if value: # TODO redis cache is broken for now 2025-08-04
            return None
#            return _update_feed_seq(
#                cached_layer,
#                schemas.FeedSequence.model_validate_json(value),
#                full_answers=full_answers,
#            )
        activities = await get_activities_v2(
            cached_layer = self,
            before_activity_id=before_activity_id,
            limit=limit,
            receiver_user_id=current_user_id,
            subject_user_uuid=subject_user_uuid,
        )

        insufficient = limit - len(activities)
        tolerate_order = before_activity_id is None
        if random:
            tolerate_order = True

        if (
            tolerate_order
            and insufficient > 0
            and subject_user_uuid is None
        ):
            random = True
            extra_activities = get_random_activities(
                receiver_user_id=current_user_id,
                before_activity_id=before_activity_id,
                limit=limit,
            )
            activities.extend(extra_activities)

        redis.delete(key)
        redis.set( # TODO fixme
            key,
            json.dumps(jsonable_encoder(1)),
            ex=datetime.timedelta(minutes=1),
        )
        return activities



    def get_user_contributions(self, user: models.User) -> UserContributions:
        if user.id in self._user_contributions_map:
            return self._user_contributions_map[user.id]

        def f() -> UserContributions:
            return self.compute_user_contributions_map(user)

        matrix = self._get_cached(
            key=USER_CONTRIBUTIONS_MAP_CACHE_KEY.format(user_id=user.id),
            typeObj=UserContributions,
            fetch=f,
            hours=24,
        )
        self._user_contributions_map[user.id] = matrix
        return matrix

    def get_related_user(self, target_user: models.User) -> List[UserPreview]:
        db = self.get_db()

        def f() -> List[UserPreview]:
            related_users: Dict[int, models.User] = {}
            followed = list(target_user.followed)
            if len(followed) >= MAX_SAMPLED_RELATED_FOLLOWED:
                for u in random.sample(followed, k=20):
                    related_users[u.id] = u
            else:
                for u in followed:
                    related_users[u.id] = u

            for user_id in self.get_similar_entity_ids(
                id=target_user.id, entity_type=EntityType.users, topK=20
            ):
                if user_id not in related_users:
                    related_users[user_id] = unwrap(crud.user.get(db, user_id))

            return [self.preview_of_user(u) for u in related_users.values()]

        return self._get_cached(
            key=RELATED_USERS_CACHE_KEY.format(user_id=target_user.id),
            typeObj=List[UserPreview],
            fetch=f,
            hours=24,
        )

    def get_similar_entity_ids(
        self, id: int, entity_type: EntityType, topK: int = 10
    ) -> List[int]:
        m = self.get_entity_similarity_matrix(entity_type=entity_type)
        if id not in m:
            return []
        return m[id][:topK]

    def request_text(self, url: str) -> Optional[str]:
        def f() -> Optional[str]:
            try:
                response = requests.get(
                    url,
                    timeout=1,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36"
                    },
                )
                if response.ok:
                    return response.text
            except Exception as e:
                sentry_sdk.capture_exception(e)
            return None

        return self._get_cached(
            key=REQUEST_TEXT_CACHE_KEY.format(url=url),
            typeObj=Optional[str],
            fetch=f,
            hours=24,
        )

    def get_site_profiles(self) -> List[schemas.Profile]:
        user_id = self.unwrapped_principal_id()
        db = self.get_db()

        def f() -> List[schemas.Profile]:
            current_user = crud.user.get(db, id=user_id)
            assert current_user is not None
            return [
                self.materializer.profile_schema_from_orm(p)
                for p in rank_site_profiles(current_user.profiles)
            ]

        return self._get_cached(
            key=USER_SITE_PROFILES.format(user_id=user_id),
            typeObj=List[schemas.Profile],
            fetch=f,
            hours=24,
        )

    def create_site_profile(
        self, *, owner: models.User, site_uuid: str
    ) -> schemas.Profile:
        data = crud.profile.create_with_owner(
            self.get_db(),
            obj_in=schemas.ProfileCreate(
                owner_uuid=owner.uuid,
                site_uuid=site_uuid,
            ),
        )
        self.get_redis().delete(USER_SITE_PROFILES.format(user_id=owner.id))
        return self.materializer.profile_schema_from_orm(data)

    def remove_site_profile(self, *, owner_id: int, site_id: int) -> None:
        crud.profile.remove_by_user_and_site(
            self.get_db(), owner_id=owner_id, site_id=site_id
        )
        self.get_redis().delete(USER_SITE_PROFILES.format(user_id=owner_id))


    # TODO maybe this is not the best place to put it  2025-Jul-06
    async def try_consume_invitation_link_by_uuid(
            self, invitation_uuid:str) -> bool:
        logger.info(f"Consumed invitation link uuid=${invitation_uuid}")
        db = self.get_db()
        invitation_link = crud.invitation_link.get_by_uuid(db, uuid=invitation_uuid)
        if invitation_link is None:
            logger.info(f"Invalid invitation uuid=${invitation_uuid}")
            return False
        logger.info("got in db " + str(invitation_link))
        if invitation_link.remaining_quota < 1:
            logger.info(f"Invitation quota has exceeded limit uuid=${invitation_uuid}")
            return False
        invitation_link.remaining_quota -= 1
        db.add(invitation_link)
        db.commit()
        return True
