"""Current-user (/me) domain service."""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from fastapi.encoders import jsonable_encoder
from pydantic.tools import parse_obj_as

from chafan_core.app import crud, schemas
from chafan_core.app.common import get_redis_cli
from chafan_core.app.responders import misc as misc_responder
from chafan_core.app.responders.user import user_schema_from_orm
from chafan_core.app.schemas.event import EventInternal, FollowUserInternal
from chafan_core.app.schemas.user import (
    UserUpdateLoginPhoneNumber,
    UserUpdateMe,
    UserUpdatePrimaryEmail,
    UserUpdateSecondaryEmails,
)
from chafan_core.app.services import people as people_service
from chafan_core.app.services import sites as sites_service
from chafan_core.app.services import submissions as submissions_service
from chafan_core.utils.base import HTTPException_
from chafan_core.utils.validators import CaseInsensitiveEmailStr


def get_me(ctx) -> schemas.User:
    return user_schema_from_orm(ctx.get_current_active_user())


def update_me(ctx, *, user_in: UserUpdateMe) -> schemas.User:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    user_in_dict = user_in.dict(exclude_unset=True)
    if user_in.handle is not None:
        if user_in.handle == "":
            raise HTTPException_(
                status_code=400,
                detail="The username can't be empty",
            )
        user = crud.user.get_by_handle(ctx.get_db(), handle=user_in.handle)
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


def update_login_email(ctx, *, user_in: UserUpdatePrimaryEmail) -> schemas.User:
    dict_in: Dict[str, Any] = {"email": user_in.email}
    existing_secondary_emails = []
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
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


def update_secondary_emails(
    ctx, *, user_in: UserUpdateSecondaryEmails
) -> schemas.User:
    existing_secondary_emails = []
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    if current_user.secondary_emails:
        existing_secondary_emails = parse_obj_as(
            List[CaseInsensitiveEmailStr], current_user.secondary_emails
        )
    dict_in: Dict[str, Any] = {}
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


def update_phone_number(
    ctx, *, user_in: UserUpdateLoginPhoneNumber
) -> schemas.User:
    dict_in: Dict[str, Any] = {}
    redis_cli = ctx.get_redis()
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
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


def get_follows(ctx, *, uuid: str) -> schemas.UserFollows:
    followed = crud.user.get_by_uuid(ctx.get_db(), uuid=uuid)
    if followed is None:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exist in the system.",
        )
    return people_service.get_user_follows(ctx, followed)


def follow_user(ctx, *, uuid: str) -> schemas.UserFollows:
    current_user = ctx.get_current_active_user()
    if uuid == current_user.uuid:
        raise HTTPException_(
            status_code=400,
            detail="User can't follow self.",
        )
    db = ctx.get_db()
    followed_user = crud.user.get_by_uuid(db, uuid=uuid)
    if followed_user is None:
        raise HTTPException_(
            status_code=400,
            detail="The followed_user doesn't exist in the system.",
        )
    followed_user = crud.user.add_follower(
        db, db_obj=followed_user, follower=current_user
    )
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    crud.notification.create_with_content(
        ctx,
        receiver_id=followed_user.id,
        event=EventInternal(
            created_at=utc_now,
            content=FollowUserInternal(
                subject_id=current_user.id,
                user_id=followed_user.id,
            ),
        ),
    )
    return schemas.UserFollows(
        user_uuid=uuid,
        followers_count=followed_user.followers.count(),
        followed_count=followed_user.followed.count(),  # type: ignore
        followed_by_me=True,
    )


def cancel_follow_user(ctx, *, uuid: str) -> schemas.UserFollows:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    followed_user = crud.user.get_by_uuid(db, uuid=uuid)
    if followed_user is None:
        raise HTTPException_(
            status_code=400,
            detail="The followed_user doesn't exist in the system.",
        )
    followed_user = crud.user.remove_follower(
        db, db_obj=followed_user, follower=current_user
    )
    return schemas.UserFollows(
        user_uuid=uuid,
        followers_count=followed_user.followers.count(),
        followed_count=followed_user.followed.count(),  # type: ignore
        followed_by_me=False,
    )


def list_channels(ctx) -> List[schemas.Channel]:
    current_user = ctx.get_current_active_user()
    mat = ctx.principal_view
    return [
        misc_responder.channel_schema_from_orm(mat, ch)
        for ch in current_user.channels
    ]


def list_my_article_columns(ctx) -> List[schemas.ArticleColumn]:
    current_user = ctx.get_current_active_user()
    mat = ctx.principal_view
    return [
        misc_responder.article_column_schema_from_orm(mat, c)
        for c in current_user.article_columns
    ]


def get_question_subscription(ctx, *, uuid: str) -> schemas.UserQuestionSubscription:
    from chafan_core.app.services import questions as questions_service

    question = questions_service.get_question_model_http(ctx.get_db(), uuid)
    return questions_service.get_question_subscription(ctx, question)


def list_subscribed_questions(
    ctx, *, skip: int, limit: int
) -> List[Optional[schemas.QuestionPreview]]:
    current_user = ctx.get_current_active_user()
    mat = ctx.principal_view
    return [
        mat.preview_of_question(q)
        for q in current_user.subscribed_questions[skip : skip + limit]
    ]


def subscribe_question(ctx, *, uuid: str) -> schemas.UserQuestionSubscription:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    question = crud.question.get_by_uuid(db, uuid=uuid)
    if question is None:
        raise HTTPException_(
            status_code=400,
            detail="The question doesn't exist in the system.",
        )
    current_user = crud.user.subscribe_question(
        db, db_obj=current_user, question=question
    )
    return schemas.UserQuestionSubscription(
        question_uuid=question.uuid,
        subscription_count=question.subscribers.count(),
        subscribed_by_me=(question in current_user.subscribed_questions),
    )


def unsubscribe_question(ctx, *, uuid: str) -> schemas.UserQuestionSubscription:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    question = crud.question.get_by_uuid(db, uuid=uuid)
    if question is None:
        raise HTTPException_(
            status_code=400,
            detail="The question doesn't exist in the system.",
        )
    current_user = crud.user.unsubscribe_question(
        db, db_obj=current_user, question=question
    )
    return schemas.UserQuestionSubscription(
        question_uuid=question.uuid,
        subscription_count=question.subscribers.count(),
        subscribed_by_me=(question in current_user.subscribed_questions),
    )


def get_submission_subscription(
    ctx, *, uuid: str
) -> schemas.UserSubmissionSubscription:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    submission = crud.submission.get_by_uuid(db, uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exist in the system.",
        )
    return schemas.UserSubmissionSubscription(
        submission_uuid=submission.uuid,
        subscription_count=submission.subscribers.count(),
        subscribed_by_me=(submission in current_user.subscribed_submissions),
    )


def list_subscribed_submissions(
    ctx, *, skip: int, limit: int
) -> List[Optional[schemas.Submission]]:
    current_user = ctx.get_current_active_user()
    return [
        submissions_service.submission_schema(ctx, q)
        for q in current_user.subscribed_submissions[skip : skip + limit]
    ]


def subscribe_submission(ctx, *, uuid: str) -> schemas.UserSubmissionSubscription:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    submission = crud.submission.get_by_uuid(db, uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exist in the system.",
        )
    current_user = crud.user.subscribe_submission(
        db, db_obj=current_user, submission=submission
    )
    return schemas.UserSubmissionSubscription(
        submission_uuid=submission.uuid,
        subscription_count=submission.subscribers.count(),
        subscribed_by_me=(submission in current_user.subscribed_submissions),
    )


def unsubscribe_submission(ctx, *, uuid: str) -> schemas.UserSubmissionSubscription:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    submission = crud.submission.get_by_uuid(db, uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exist in the system.",
        )
    current_user = crud.user.unsubscribe_submission(
        db, db_obj=current_user, submission=submission
    )
    return schemas.UserSubmissionSubscription(
        submission_uuid=submission.uuid,
        subscription_count=submission.subscribers.count(),
        subscribed_by_me=(submission in current_user.subscribed_submissions),
    )


def list_bookmarked_answers(
    ctx, *, skip: int, limit: int
) -> List[Optional[schemas.AnswerPreview]]:
    current_user = ctx.get_current_active_user()
    mat = ctx.principal_view
    return [
        mat.preview_of_answer(answer)
        for answer in current_user.bookmarked_answers[skip : skip + limit]
    ]


def bookmark_answer(ctx, *, uuid: str) -> schemas.UserAnswerBookmark:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exist in the system.",
        )
    current_user = crud.user.bookmark_answer(db, db_obj=current_user, answer=answer)
    return schemas.UserAnswerBookmark(
        answer_uuid=answer.uuid,
        bookmarkers_count=answer.bookmarkers.count(),
        bookmarked_by_me=(answer in current_user.bookmarked_answers),
    )


def unbookmark_answer(ctx, *, uuid: str) -> schemas.UserAnswerBookmark:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exist in the system.",
        )
    current_user = crud.user.unbookmark_answer(db, db_obj=current_user, answer=answer)
    return schemas.UserAnswerBookmark(
        answer_uuid=answer.uuid,
        bookmarkers_count=answer.bookmarkers.count(),
        bookmarked_by_me=(answer in current_user.bookmarked_answers),
    )


def list_bookmarked_articles(
    ctx, *, skip: int, limit: int
) -> List[Optional[schemas.ArticlePreview]]:
    current_user = ctx.get_current_active_user()
    mat = ctx.principal_view
    return [
        mat.preview_of_article(article)
        for article in current_user.bookmarked_articles[skip : skip + limit]
    ]


def bookmark_article(ctx, *, uuid: str) -> schemas.UserArticleBookmark:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    article = crud.article.get_by_uuid(db, uuid=uuid)
    if article is None:
        raise HTTPException_(
            status_code=400,
            detail="The article doesn't exist in the system.",
        )
    current_user = crud.user.bookmark_article(db, db_obj=current_user, article=article)
    return schemas.UserArticleBookmark(
        article_uuid=article.uuid,
        bookmarkers_count=article.bookmarkers.count(),
        bookmarked_by_me=(article in current_user.bookmarked_articles),
    )


def unbookmark_article(ctx, *, uuid: str) -> schemas.UserArticleBookmark:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    article = crud.article.get_by_uuid(db, uuid=uuid)
    if article is None:
        raise HTTPException_(
            status_code=400,
            detail="The article doesn't exist in the system.",
        )
    current_user = crud.user.unbookmark_article(
        db, db_obj=current_user, article=article
    )
    return schemas.UserArticleBookmark(
        article_uuid=article.uuid,
        bookmarkers_count=article.bookmarkers.count(),
        bookmarked_by_me=(article in current_user.bookmarked_articles),
    )


def get_topic_subscription(ctx, *, uuid: str) -> schemas.UserTopicSubscription:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    topic = crud.topic.get_by_uuid(db, uuid=uuid)
    if topic is None:
        raise HTTPException_(
            status_code=400,
            detail="The topic doesn't exist in the system.",
        )
    return schemas.UserTopicSubscription(
        topic_uuid=topic.uuid,
        subscription_count=topic.subscribers.count(),
        subscribed_by_me=(topic in current_user.subscribed_topics),
    )


def subscribe_topic(ctx, *, uuid: str) -> schemas.UserTopicSubscription:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    topic = crud.topic.get_by_uuid(db, uuid=uuid)
    if topic is None:
        raise HTTPException_(
            status_code=400,
            detail="The topic doesn't exist in the system.",
        )
    current_user = crud.user.subscribe_topic(db, db_obj=current_user, topic=topic)
    return schemas.UserTopicSubscription(
        topic_uuid=topic.uuid,
        subscription_count=topic.subscribers.count(),
        subscribed_by_me=(topic in current_user.subscribed_topics),
    )


def unsubscribe_topic(ctx, *, uuid: str) -> schemas.UserTopicSubscription:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    topic = crud.topic.get_by_uuid(db, uuid=uuid)
    if topic is None:
        raise HTTPException_(
            status_code=400,
            detail="The topic doesn't exist in the system.",
        )
    current_user = crud.user.unsubscribe_topic(db, db_obj=current_user, topic=topic)
    return schemas.UserTopicSubscription(
        topic_uuid=topic.uuid,
        subscription_count=topic.subscribers.count(),
        subscribed_by_me=(topic in current_user.subscribed_topics),
    )


def get_article_column_subscription(
    ctx, *, uuid: str
) -> schemas.UserArticleColumnSubscription:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    article_column = crud.article_column.get_by_uuid(db, uuid=uuid)
    if article_column is None:
        raise HTTPException_(
            status_code=400,
            detail="The article_column doesn't exist in the system.",
        )
    return schemas.UserArticleColumnSubscription(
        article_column_uuid=article_column.uuid,
        subscription_count=article_column.subscribers.count(),
        subscribed_by_me=(article_column in current_user.subscribed_article_columns),
    )


def list_subscribed_article_columns(ctx) -> List[schemas.ArticleColumn]:
    current_user = ctx.get_current_active_user()
    mat = ctx.principal_view
    return [
        misc_responder.article_column_schema_from_orm(mat, c)
        for c in current_user.subscribed_article_columns
    ]


def subscribe_article_column(
    ctx, *, uuid: str
) -> schemas.UserArticleColumnSubscription:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    article_column = crud.article_column.get_by_uuid(db, uuid=uuid)
    if article_column is None:
        raise HTTPException_(
            status_code=400,
            detail="The article_column doesn't exist in the system.",
        )
    current_user = crud.user.subscribe_article_column(
        db, db_obj=current_user, article_column=article_column
    )
    return schemas.UserArticleColumnSubscription(
        article_column_uuid=article_column.uuid,
        subscription_count=article_column.subscribers.count(),
        subscribed_by_me=(article_column in current_user.subscribed_article_columns),
    )


def get_article_column_subscription_after_unsubscribe(
    ctx, *, uuid: str
) -> schemas.UserArticleColumnSubscription:
    """Historical endpoint behavior: return subscription state only (no unsubscribe)."""
    db = ctx.get_db()
    article_column = crud.article_column.get_by_uuid(db, uuid=uuid)
    if article_column is None:
        raise HTTPException_(
            status_code=400,
            detail="The article_column doesn't exist in the system.",
        )
    return misc_responder.get_user_article_column_subscription(
        ctx.principal_view, article_column
    )


def list_site_profiles(ctx) -> List[schemas.Profile]:
    return sites_service.site_profiles_for_user(
        ctx.get_db(),
        ctx.principal_view,
        ctx.unwrapped_principal_id(),
    )


def list_moderated_sites(ctx) -> List[schemas.Site]:
    current_user = ctx.get_current_active_user()
    if current_user.is_superuser:
        sites = crud.site.get_all(ctx.get_db())
    else:
        sites = current_user.moderated_sites
    return [sites_service.site_schema(ctx, s) for s in sites]
