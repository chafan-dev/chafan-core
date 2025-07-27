import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from pydantic.tools import parse_obj_as

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import get_redis_cli
from chafan_core.app.materialize import user_schema_from_orm
from chafan_core.app.schemas.event import EventInternal, FollowUserInternal
from chafan_core.app.schemas.user import (
    UserUpdateLoginPhoneNumber,
    UserUpdateMe,
    UserUpdatePrimaryEmail,
    UserUpdateSecondaryEmails,
)
from chafan_core.utils.base import HTTPException_
from chafan_core.utils.constants import MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT
from chafan_core.utils.validators import CaseInsensitiveEmailStr

router = APIRouter()


############################## User self-management ##############################


# NOTE: don't change route to "/"
@router.get("", response_model=schemas.User)
def read_user_me(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
) -> Any:
    """
    Get current user.
    """
    return user_schema_from_orm(cached_layer.get_current_active_user())


# NOTE: don't change route to "/"
@router.put("", response_model=schemas.User)
def update_user_me(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    user_in: UserUpdateMe,
) -> Any:
    """
    Update own user.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    user_in_dict = user_in.dict(exclude_unset=True)
    if user_in.handle is not None:
        if user_in.handle == "":
            raise HTTPException_(
                status_code=400,
                detail="The username can't be empty",
            )
        user = crud.user.get_by_handle(cached_layer.get_db(), handle=user_in.handle)
        if user is not None and user != current_user:
            raise HTTPException_(
                status_code=400,
                detail="The user with this username already exists in the system",
            )
    if user_in.residency_topic_uuids is not None:
        new_topics = []
        for topic_uuid in user_in.residency_topic_uuids:
            topic = crud.topic.get_by_uuid(db, uuid=topic_uuid)
            if topic is None:
                raise HTTPException_(
                    status_code=400,
                    detail="The topic doesn't exist.",
                )
            new_topics.append(topic)
        del user_in_dict["residency_topic_uuids"]
        crud.user.update_residency_topics(
            db, db_obj=current_user, new_topics=new_topics
        )
    if user_in.profession_topic_uuids is not None:
        new_topics = []
        for topic_uuid in user_in.profession_topic_uuids:
            topic = crud.topic.get_by_uuid(db, uuid=topic_uuid)
            if topic is None:
                raise HTTPException_(
                    status_code=400,
                    detail="The topic doesn't exist.",
                )
            new_topics.append(topic)
        del user_in_dict["profession_topic_uuids"]
        crud.user.update_profession_topics(
            db, db_obj=current_user, new_topics=new_topics
        )
    if user_in.education_experiences is not None:
        current_user.education_experiences = jsonable_encoder(
            user_in.education_experiences
        )
        del user_in_dict["education_experiences"]
    if user_in.work_experiences is not None:
        current_user.work_experiences = jsonable_encoder(user_in.work_experiences)
        del user_in_dict["work_experiences"]
    if user_in.flag_list is not None:
        user_in_dict["flags"] = " ".join(user_in.flag_list)
        del user_in_dict["flag_list"]
    return user_schema_from_orm(
        crud.user.update(db, db_obj=current_user, obj_in=user_in_dict)
    )


@router.put("/login", response_model=schemas.User)
def update_user_login_email(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    user_in: UserUpdatePrimaryEmail,
) -> Any:
    dict_in: Dict[str, Any] = {"email": user_in.email}
    existing_secondary_emails = []
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    if crud.user.get_by_email(db, email=user_in.email) is not None:
        raise HTTPException_(
            status_code=400,
            detail="This primary email is already used in the website.",
        )
    if current_user.secondary_emails:
        existing_secondary_emails = parse_obj_as(
            List[CaseInsensitiveEmailStr], current_user.secondary_emails
        )
    if user_in.email in existing_secondary_emails:
        existing_secondary_emails.remove(user_in.email)
        dict_in["secondary_emails"] = existing_secondary_emails + [
            parse_obj_as(CaseInsensitiveEmailStr, current_user.email)
        ]
        return user_schema_from_orm(
            crud.user.update(db, db_obj=current_user, obj_in=dict_in)
        )
    elif user_in.verification_code:
        redis_cli = get_redis_cli()
        key = f"chafan:verification-code:{user_in.email}"
        value = redis_cli.get(key)
        if value is None:
            raise HTTPException_(
                status_code=400,
                detail="The verification code is not present in the system.",
            )
        if value != user_in.verification_code:
            raise HTTPException_(
                status_code=400,
                detail="Invalid verification code.",
            )
        redis_cli.delete(key)
        dict_in["secondary_emails"] = existing_secondary_emails + [
            parse_obj_as(CaseInsensitiveEmailStr, current_user.email)
        ]
        return user_schema_from_orm(
            crud.user.update(db, db_obj=current_user, obj_in=dict_in)
        )
    else:
        raise HTTPException_(
            status_code=400,
            detail="Must provide verification code for non-secondary email.",
        )


@router.put("/secondary-emails", response_model=schemas.User)
def update_user_secondary_emails(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    user_in: UserUpdateSecondaryEmails,
) -> Any:
    existing_secondary_emails = []
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    if current_user.secondary_emails:
        existing_secondary_emails = parse_obj_as(
            List[CaseInsensitiveEmailStr], current_user.secondary_emails
        )
    dict_in = {}
    if user_in.action == "add":
        if not user_in.verification_code:
            raise HTTPException_(
                status_code=400,
                detail="Must provide verification code for adding new secondary email.",
            )
        if user_in.secondary_email in existing_secondary_emails:
            raise HTTPException_(
                status_code=400,
                detail="The secondary email already exists.",
            )
        redis_cli = get_redis_cli()
        key = f"chafan:verification-code:{user_in.secondary_email}"
        value = redis_cli.get(key)
        if value is None:
            raise HTTPException_(
                status_code=400,
                detail="The verification code is not present in the system.",
            )
        if value != user_in.verification_code:
            raise HTTPException_(
                status_code=400,
                detail="Invalid verification code.",
            )
        redis_cli.delete(key)
        dict_in["secondary_emails"] = existing_secondary_emails + [
            user_in.secondary_email
        ]
        return user_schema_from_orm(
            crud.user.update(db, db_obj=current_user, obj_in=dict_in)
        )
    elif user_in.action == "remove":
        if user_in.secondary_email not in existing_secondary_emails:
            raise HTTPException_(
                status_code=400,
                detail="The secondary email doesn't exist.",
            )
        existing_secondary_emails.remove(user_in.secondary_email)
        dict_in["secondary_emails"] = existing_secondary_emails
        return user_schema_from_orm(
            crud.user.update(db, db_obj=current_user, obj_in=dict_in)
        )
    else:
        raise HTTPException_(
            status_code=400,
            detail="Invalid input.",
        )


@router.put("/phone-number", response_model=schemas.User)
def update_user_phone_number(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    user_in: UserUpdateLoginPhoneNumber,
) -> Any:
    dict_in = {}
    redis_cli = cached_layer.get_redis()
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    phone_str = user_in.phone_number.format_e164()
    dict_in["phone_number"] = phone_str
    key = f"chafan:verification-code:{phone_str}"
    value = redis_cli.get(key)
    if value is None:
        raise HTTPException_(
            status_code=400,
            detail="The verification code is not present in the system.",
        )
    if value != user_in.verification_code:
        raise HTTPException_(
            status_code=400,
            detail="Invalid verification code.",
        )
    redis_cli.delete(key)
    return user_schema_from_orm(
        crud.user.update(db, db_obj=current_user, obj_in=dict_in)
    )


######################### User Follows User #########################


@router.get("/follows/{uuid}", response_model=schemas.UserFollows)
def get_user_follows(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    uuid: str,
) -> Any:
    """
    Get a user's follows info.
    """
    followed = crud.user.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if followed is None:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exists in the system.",
        )
    return cached_layer.get_user_follows(followed)


@router.post("/follows/{uuid}", response_model=schemas.UserFollows)
def follow_user(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
) -> Any:
    """
    Follow a user.
    """
    current_user = cached_layer.get_current_active_user()
    if uuid == current_user.uuid:
        raise HTTPException_(
            status_code=400,
            detail="User can't follow self.",
        )
    db = cached_layer.get_db()
    followed_user = crud.user.get_by_uuid(db, uuid=uuid)
    if followed_user is None:
        raise HTTPException_(
            status_code=400,
            detail="The followed_user doesn't exists in the system.",
        )
    followed_user = crud.user.add_follower(
        db, db_obj=followed_user, follower=current_user
    )
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    crud.notification.create_with_content(
        cached_layer.broker,
        receiver_id=followed_user.id,
        event=EventInternal(
            created_at=utc_now,
            content=FollowUserInternal(
                subject_id=current_user.id,
                user_id=followed_user.id,
            ),
        ),
    )
    data = schemas.UserFollows(
        user_uuid=uuid,
        followers_count=followed_user.followers.count(),
        followed_count=followed_user.followed.count(),  # type: ignore
        followed_by_me=True,
    )
    return data


@router.delete("/follows/{uuid}", response_model=schemas.UserFollows)
def cancel_follow_user(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Cancel follow of user.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    followed_user = crud.user.get_by_uuid(db, uuid=uuid)
    if followed_user is None:
        raise HTTPException_(
            status_code=400,
            detail="The followed_user doesn't exists in the system.",
        )
    followed_user = crud.user.remove_follower(
        db, db_obj=followed_user, follower=current_user
    )
    data = schemas.UserFollows(
        user_uuid=uuid,
        followers_count=followed_user.followers.count(),
        followed_count=followed_user.followed.count(),  # type: ignore
        followed_by_me=False,
    )
    return data


@router.get("/channels/", response_model=List[schemas.Channel])
def get_user_channels(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
) -> Any:
    """
    Get a user's all channels.
    """
    current_user = cached_layer.get_current_active_user()
    return [cached_layer.channel_schema_from_orm(ch) for ch in current_user.channels]


@router.get("/article-columns/", response_model=List[schemas.ArticleColumn])
def get_user_article_columns(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
) -> Any:
    """
    Get a user's all article_columns.
    """
    current_user = cached_layer.get_current_active_user()
    return [
        cached_layer.materializer.article_column_schema_from_orm(c)
        for c in current_user.article_columns
    ]


######################### User Subscribes Question #########################


@router.get(
    "/question-subscriptions/{uuid}", response_model=schemas.UserQuestionSubscription
)
def get_user_question_subscription(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Get current user's info about a question's subscription.
    """
    question = cached_layer.get_question_model_http(uuid)
    return cached_layer.get_question_subscription(question)


@router.get(
    "/question-subscriptions/", response_model=List[Optional[schemas.QuestionPreview]]
)
def get_user_question_subscriptions(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT,
        le=MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    """
    Get current user's subscribed questions.
    """
    current_user = cached_layer.get_current_active_user()
    return [
        cached_layer.materializer.preview_of_question(q)
        for q in current_user.subscribed_questions[skip : skip + limit]
    ]


@router.post(
    "/question-subscriptions/{uuid}", response_model=schemas.UserQuestionSubscription
)
def subscribe_question(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Subscribe a question.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    question = crud.question.get_by_uuid(db, uuid=uuid)
    if question is None:
        raise HTTPException_(
            status_code=400,
            detail="The question doesn't exists in the system.",
        )
    current_user = crud.user.subscribe_question(
        db, db_obj=current_user, question=question
    )
    return schemas.UserQuestionSubscription(
        question_uuid=question.uuid,
        subscription_count=question.subscribers.count(),
        subscribed_by_me=(question in current_user.subscribed_questions),
    )


@router.delete(
    "/question-subscriptions/{uuid}", response_model=schemas.UserQuestionSubscription
)
def unsubscribe_question(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Unsubscribe a question.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    question = crud.question.get_by_uuid(db, uuid=uuid)
    if question is None:
        raise HTTPException_(
            status_code=400,
            detail="The question doesn't exists in the system.",
        )
    current_user = crud.user.unsubscribe_question(
        db, db_obj=current_user, question=question
    )
    return schemas.UserQuestionSubscription(
        question_uuid=question.uuid,
        subscription_count=question.subscribers.count(),
        subscribed_by_me=(question in current_user.subscribed_questions),
    )


######################### User Subscribes Submission #########################


@router.get(
    "/submission-subscriptions/{uuid}",
    response_model=schemas.UserSubmissionSubscription,
)
def get_user_submission_subscription(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Get current user's info about a submission's subscription.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    submission = crud.submission.get_by_uuid(db, uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exists in the system.",
        )
    return schemas.UserSubmissionSubscription(
        submission_uuid=submission.uuid,
        subscription_count=submission.subscribers.count(),
        subscribed_by_me=(submission in current_user.subscribed_submissions),
    )


@router.get(
    "/submission-subscriptions/", response_model=List[Optional[schemas.Submission]]
)
def get_user_submission_subscriptions(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT,
        le=MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    """
    Get current user's subscribed submissions.
    """
    current_user = cached_layer.get_current_active_user()
    return [
        cached_layer.submission_schema_from_orm(q)
        for q in current_user.subscribed_submissions[skip : skip + limit]
    ]


@router.post(
    "/submission-subscriptions/{uuid}",
    response_model=schemas.UserSubmissionSubscription,
)
def subscribe_submission(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Subscribe a submission.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    submission = crud.submission.get_by_uuid(db, uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exists in the system.",
        )
    current_user = crud.user.subscribe_submission(
        db, db_obj=current_user, submission=submission
    )
    return schemas.UserSubmissionSubscription(
        submission_uuid=submission.uuid,
        subscription_count=submission.subscribers.count(),
        subscribed_by_me=(submission in current_user.subscribed_submissions),
    )


@router.delete(
    "/submission-subscriptions/{uuid}",
    response_model=schemas.UserSubmissionSubscription,
)
def unsubscribe_submission(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Unsubscribe a submission.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    submission = crud.submission.get_by_uuid(db, uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exists in the system.",
        )
    current_user = crud.user.unsubscribe_submission(
        db, db_obj=current_user, submission=submission
    )
    return schemas.UserSubmissionSubscription(
        submission_uuid=submission.uuid,
        subscription_count=submission.subscribers.count(),
        subscribed_by_me=(submission in current_user.subscribed_submissions),
    )


######################### User bookmarks answer #########################


@router.get("/answer-bookmarks/", response_model=List[Optional[schemas.AnswerPreview]])
def get_user_answer_bookmarks(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT,
        le=MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    current_user = cached_layer.get_current_active_user()
    return [
        cached_layer.materializer.preview_of_answer(answer)
        for answer in current_user.bookmarked_answers[skip : skip + limit]
    ]


@router.post("/answer-bookmarks/{uuid}", response_model=schemas.UserAnswerBookmark)
def bookmark_answer(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exists in the system.",
        )
    current_user = crud.user.bookmark_answer(db, db_obj=current_user, answer=answer)
    return schemas.UserAnswerBookmark(
        answer_uuid=answer.uuid,
        bookmarkers_count=answer.bookmarkers.count(),
        bookmarked_by_me=(answer in current_user.bookmarked_answers),
    )


@router.delete("/answer-bookmarks/{uuid}", response_model=schemas.UserAnswerBookmark)
def unbookmark_answer(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exists in the system.",
        )
    current_user = crud.user.unbookmark_answer(db, db_obj=current_user, answer=answer)
    return schemas.UserAnswerBookmark(
        answer_uuid=answer.uuid,
        bookmarkers_count=answer.bookmarkers.count(),
        bookmarked_by_me=(answer in current_user.bookmarked_answers),
    )


@router.get(
    "/article-bookmarks/", response_model=List[Optional[schemas.ArticlePreview]]
)
def get_user_article_bookmarks(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT,
        le=MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    current_user = cached_layer.get_current_active_user()
    return [
        cached_layer.materializer.preview_of_article(article)
        for article in current_user.bookmarked_articles[skip : skip + limit]
    ]


@router.post("/article-bookmarks/{uuid}", response_model=schemas.UserArticleBookmark)
def bookmark_article(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    article = crud.article.get_by_uuid(db, uuid=uuid)
    if article is None:
        raise HTTPException_(
            status_code=400,
            detail="The article doesn't exists in the system.",
        )
    current_user = crud.user.bookmark_article(db, db_obj=current_user, article=article)
    return schemas.UserArticleBookmark(
        article_uuid=article.uuid,
        bookmarkers_count=article.bookmarkers.count(),
        bookmarked_by_me=(article in current_user.bookmarked_articles),
    )


@router.delete("/article-bookmarks/{uuid}", response_model=schemas.UserArticleBookmark)
def unbookmark_article(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    article = crud.article.get_by_uuid(db, uuid=uuid)
    if article is None:
        raise HTTPException_(
            status_code=400,
            detail="The article doesn't exists in the system.",
        )
    current_user = crud.user.unbookmark_article(
        db, db_obj=current_user, article=article
    )
    return schemas.UserArticleBookmark(
        article_uuid=article.uuid,
        bookmarkers_count=article.bookmarkers.count(),
        bookmarked_by_me=(article in current_user.bookmarked_articles),
    )


######################### User Subscribes Topic #########################


@router.get("/topic-subscriptions/{uuid}", response_model=schemas.UserTopicSubscription)
def get_user_topic_subscription(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Get current user's info about a topic's subscription.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    topic = crud.topic.get_by_uuid(db, uuid=uuid)
    if topic is None:
        raise HTTPException_(
            status_code=400,
            detail="The topic doesn't exists in the system.",
        )
    return schemas.UserTopicSubscription(
        topic_uuid=topic.uuid,
        subscription_count=topic.subscribers.count(),
        subscribed_by_me=(topic in current_user.subscribed_topics),
    )


@router.post(
    "/topic-subscriptions/{uuid}", response_model=schemas.UserTopicSubscription
)
def subscribe_topic(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Subscribe a topic.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    topic = crud.topic.get_by_uuid(db, uuid=uuid)
    if topic is None:
        raise HTTPException_(
            status_code=400,
            detail="The topic doesn't exists in the system.",
        )
    current_user = crud.user.subscribe_topic(db, db_obj=current_user, topic=topic)
    return schemas.UserTopicSubscription(
        topic_uuid=topic.uuid,
        subscription_count=topic.subscribers.count(),
        subscribed_by_me=(topic in current_user.subscribed_topics),
    )


@router.delete(
    "/topic-subscriptions/{uuid}", response_model=schemas.UserTopicSubscription
)
def unsubscribe_topic(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Unsubscribe a topic.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    topic = crud.topic.get_by_uuid(db, uuid=uuid)
    if topic is None:
        raise HTTPException_(
            status_code=400,
            detail="The topic doesn't exists in the system.",
        )
    current_user = crud.user.unsubscribe_topic(db, db_obj=current_user, topic=topic)
    return schemas.UserTopicSubscription(
        topic_uuid=topic.uuid,
        subscription_count=topic.subscribers.count(),
        subscribed_by_me=(topic in current_user.subscribed_topics),
    )


######################### User Subscribes Article Column #########################


@router.get(
    "/article-column-subscriptions/{uuid}",
    response_model=schemas.UserArticleColumnSubscription,
)
def get_user_article_column_subscription(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Get current user's info about a article_column's subscription.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    article_column = crud.article_column.get_by_uuid(db, uuid=uuid)
    if article_column is None:
        raise HTTPException_(
            status_code=400,
            detail="The article_column doesn't exists in the system.",
        )
    return schemas.UserArticleColumnSubscription(
        article_column_uuid=article_column.uuid,
        subscription_count=article_column.subscribers.count(),
        subscribed_by_me=(article_column in current_user.subscribed_article_columns),
    )


@router.get(
    "/article-column-subscriptions/", response_model=List[schemas.ArticleColumn]
)
def get_user_article_column_subscriptions(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
) -> Any:
    """
    Get current user's all subscribed article columns.
    """
    current_user = cached_layer.get_current_active_user()
    return [
        cached_layer.materializer.article_column_schema_from_orm(c)
        for c in current_user.subscribed_article_columns
    ]


@router.post(
    "/article-column-subscriptions/{uuid}",
    response_model=schemas.UserArticleColumnSubscription,
)
def subscribe_article_column(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Subscribe a article_column.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    article_column = crud.article_column.get_by_uuid(db, uuid=uuid)
    if article_column is None:
        raise HTTPException_(
            status_code=400,
            detail="The article_column doesn't exists in the system.",
        )
    current_user = crud.user.subscribe_article_column(
        db, db_obj=current_user, article_column=article_column
    )
    return schemas.UserArticleColumnSubscription(
        article_column_uuid=article_column.uuid,
        subscription_count=article_column.subscribers.count(),
        subscribed_by_me=(article_column in current_user.subscribed_article_columns),
    )


@router.delete(
    "/article-column-subscriptions/{uuid}",
    response_model=schemas.UserArticleColumnSubscription,
)
def unsubscribe_article_column(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Unsubscribe a article_column.
    """
    db = cached_layer.get_db()
    article_column = crud.article_column.get_by_uuid(db, uuid=uuid)
    if article_column is None:
        raise HTTPException_(
            status_code=400,
            detail="The article_column doesn't exists in the system.",
        )
    return cached_layer.materializer.get_user_article_column_subscription(
        article_column
    )


@router.get("/site-profiles/", response_model=List[schemas.Profile])
def get_site_profiles(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
) -> Any:
    return cached_layer.get_site_profiles()


@router.get(
    "/moderated-sites/", response_model=List[schemas.Site], include_in_schema=False
)
def get_moderated_sites(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
) -> Any:
    current_user = cached_layer.get_current_active_user()
    if current_user.is_superuser:
        sites = crud.site.get_all(cached_layer.get_db())
    else:
        sites = current_user.moderated_sites
    return [cached_layer.materializer.site_schema_from_orm(s) for s in sites]
