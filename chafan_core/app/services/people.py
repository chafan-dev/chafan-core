"""People / social graph service."""

from __future__ import annotations

import random
from typing import Dict, List, Optional

from pydantic.tools import parse_obj_as
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.common import OperationType
from chafan_core.app.model_utils import is_live_answer, is_live_article
from chafan_core.app.recs import matrices as recs_matrices
from chafan_core.app.responders import misc as misc_responder
from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.schemas.user import (
    UserEducationExperienceInternal,
    UserWorkExperienceInternal,
    YearContributions,
)
from chafan_core.app.services import submissions as submissions_service
from chafan_core.app.user_permission import user_in_site
from chafan_core.utils.base import EntityType, HTTPException_, filter_not_none, unwrap

MAX_SAMPLED_RELATED_FOLLOWED = 20


def get_user_follows(
    ctx, followed: models.User
) -> schemas.UserFollows:
    current_user = ctx.try_get_current_user()
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


def preview_of_user(ctx, user: models.User) -> schemas.UserPreview:
    """User preview with social annotations for the current principal."""
    from chafan_core.app.responders import user as user_responder

    user_preview = user_responder.plain_preview_of_user(user)
    principal_id = ctx.principal_id
    if principal_id:
        m = ctx.get_follow_follow_fanout()
        if principal_id in m and user_preview.uuid in m[principal_id]:
            user_preview.social_annotations.follow_follows = m[principal_id][
                user_preview.uuid
            ]
        else:
            user_preview.social_annotations.follow_follows = 0
    user_preview.follows = get_user_follows(ctx, user)
    return user_preview


def get_followers(
    ctx, user: models.User, skip: int, limit: int
) -> List[UserPreview]:
    return [
        preview_of_user(ctx, u) for u in user.followers[skip : skip + limit]
    ]


def get_followed(
    ctx, user: models.User, skip: int, limit: int
) -> List[UserPreview]:
    return [
        preview_of_user(ctx, u) for u in user.followed[skip : skip + limit]
    ]


def get_authored_answers_for_principal(
    ctx, author: models.User
) -> List[schemas.AnswerPreview]:
    mat = ctx.principal_view
    return filter_not_none(
        [mat.preview_of_answer(answer) for answer in author.answers]
    )


def _require_user(ctx, uuid: str) -> models.User:
    user = crud.user.get_by_uuid(ctx.get_db(), uuid=uuid)
    if user is None:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exist in the system.",
        )
    return user


def list_user_site_profiles(
    ctx, *, uuid: str, current_user_id: Optional[int]
) -> List[schemas.Profile]:
    user = _require_user(ctx, uuid)
    if not user.is_active:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exist in the system.",
        )
    if not current_user_id:
        return []
    mat = ctx.principal_view
    return [
        misc_responder.profile_schema_from_orm(mat, profile)
        for profile in user.profiles
        if user_in_site(
            ctx.get_db(),
            site=profile.site,
            user_id=current_user_id,
            op_type=OperationType.ReadSite,
        )
    ]


def _work_exps(db: Session, user: models.User) -> List[schemas.UserWorkExperience]:
    work_exps: List[UserWorkExperienceInternal] = []
    if user.work_experiences is not None:
        work_exps = parse_obj_as(
            List[UserWorkExperienceInternal], user.work_experiences
        )
    ret = []
    for work_exp in work_exps:
        company_topic = crud.topic.get_by_uuid(db, uuid=work_exp.company_topic_uuid)
        position_topic = crud.topic.get_by_uuid(db, uuid=work_exp.position_topic_uuid)
        ret.append(
            schemas.UserWorkExperience(
                company_topic=schemas.Topic.from_orm(company_topic),
                position_topic=schemas.Topic.from_orm(position_topic),
            )
        )
    return ret


def _edu_exps(db: Session, user: models.User) -> List[schemas.UserEducationExperience]:
    edu_exps: List[UserEducationExperienceInternal] = []
    if user.education_experiences is not None:
        edu_exps = parse_obj_as(
            List[UserEducationExperienceInternal], user.education_experiences
        )
    ret = []
    for edu_exp in edu_exps:
        school_topic = crud.topic.get_by_uuid(db, uuid=edu_exp.school_topic_uuid)
        ret.append(
            schemas.UserEducationExperience(
                school_topic=schemas.Topic.from_orm(school_topic),
                level=edu_exp.level_name,
                major=edu_exp.major,
                enroll_year=edu_exp.enroll_year,
                graduate_year=edu_exp.graduate_year,
            )
        )
    return ret


def _user_public_schema(
    ctx, user: models.User, view_times: int
) -> schemas.UserPublic:
    """One public profile schema for any principal allowed to view the user."""
    preview = preview_of_user(ctx, user)
    db = ctx.get_db()
    about_content = None
    if user.about is not None:
        about_content = RichText(source=user.about, editor="wysiwyg")
    contributions = [
        YearContributions(year=year, data=data)
        for year, data in ctx.get_user_contributions(user)
    ]
    return schemas.UserPublic(
        **preview.dict(),
        gif_avatar_url=user.gif_avatar_url,
        answers_count=len(
            [answer for answer in user.answers if is_live_answer(answer)]
        ),
        submissions_count=len(
            [submission for submission in user.submissions if not submission.is_hidden]
        ),
        questions_count=len(
            [question for question in user.questions if not question.is_hidden]
        ),
        articles_count=len(
            [article for article in user.articles if is_live_article(article)]
        ),
        created_at=user.created_at,
        profile_view_times=view_times,
        about_content=about_content,
        profiles=[],
        residency_topics=[schemas.Topic.from_orm(t) for t in user.residency_topics],
        profession_topics=[schemas.Topic.from_orm(t) for t in user.profession_topics],
        github_username=user.github_username,
        twitter_username=user.twitter_username,
        linkedin_url=user.linkedin_url,
        homepage_url=user.homepage_url,
        zhihu_url=user.zhihu_url,
        subscribed_topics=[schemas.Topic.from_orm(t) for t in user.subscribed_topics],
        work_exps=_work_exps(db, user),
        edu_exps=_edu_exps(db, user),
        contributions=contributions,
    )


def get_user_public(ctx, *, handle: str) -> schemas.UserPublic:
    user = crud.user.get_by_handle(ctx.get_db(), handle=handle)
    if user is None or not user.is_active:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exist in the system.",
        )
    # TODO turn it off 2025-07-23
    view_times = 5  # view_counters.get_views(user.uuid, "profile")
    return _user_public_schema(ctx, user, view_times)


def list_user_work_exps(ctx, *, uuid: str) -> List[schemas.UserWorkExperience]:
    return _work_exps(ctx.get_db(), _require_user(ctx, uuid))


def list_user_edu_exps(ctx, *, uuid: str) -> List[schemas.UserEducationExperience]:
    return _edu_exps(ctx.get_db(), _require_user(ctx, uuid))


def list_user_questions(
    ctx, *, uuid: str, skip: int, limit: int
) -> List[schemas.QuestionPreview]:
    user = _require_user(ctx, uuid)
    mat = ctx.principal_view
    # FIXME: think about more efficient paging mechanism
    return filter_not_none(
        [
            mat.preview_of_question(question)
            for question in user.questions
            if not question.is_hidden
        ]
    )[skip : skip + limit]


def list_user_articles(
    ctx, *, uuid: str, skip: int, limit: int
) -> List[schemas.ArticlePreview]:
    user = _require_user(ctx, uuid)
    mat = ctx.principal_view
    # TODO we have limit, but we still generate all articles. Need generator 2025-Mar-23
    return filter_not_none(
        [mat.preview_of_article(article) for article in user.articles]
    )[skip : skip + limit]


def list_user_submissions(
    ctx, *, uuid: str, skip: int, limit: int
) -> List[schemas.Submission]:
    user = _require_user(ctx, uuid)
    return filter_not_none(
        [
            submissions_service.submission_schema(ctx, submission)
            for submission in user.submissions
        ]
    )[skip : skip + limit]


def list_user_answers(
    ctx, *, uuid: str, skip: int, limit: int
) -> List[schemas.AnswerPreview]:
    author = _require_user(ctx, uuid)
    return get_authored_answers_for_principal(ctx, author)[skip : skip + limit]


def list_user_followers(
    ctx, *, uuid: str, skip: int, limit: int
) -> List[UserPreview]:
    return get_followers(ctx, _require_user(ctx, uuid), skip=skip, limit=limit)


def list_user_followed(
    ctx, *, uuid: str, skip: int, limit: int
) -> List[UserPreview]:
    return get_followed(ctx, _require_user(ctx, uuid), skip=skip, limit=limit)


def list_related_users(ctx, *, uuid: str) -> List[UserPreview]:
    return get_related_users(ctx, unwrap(crud.user.get_by_uuid(ctx.get_db(), uuid=uuid)))


def get_related_users(ctx, target_user: models.User) -> List[UserPreview]:
    db = ctx.get_db()
    related_users: Dict[int, models.User] = {}
    followed = list(target_user.followed)
    if len(followed) >= MAX_SAMPLED_RELATED_FOLLOWED:
        for u in random.sample(followed, k=20):
            related_users[u.id] = u
    else:
        for u in followed:
            related_users[u.id] = u

    for user_id in recs_matrices.similar_entity_ids(
        db,
        entity_id=target_user.id,
        entity_type=EntityType.users,
        top_k=20,
    ):
        if user_id not in related_users:
            related_users[user_id] = unwrap(crud.user.get(db, user_id))

    return [preview_of_user(ctx, u) for u in related_users.values()]
