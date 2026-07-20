"""People / social graph service."""

from __future__ import annotations

import random
from typing import Dict, List, Optional

from chafan_core.app import crud, models, schemas
from chafan_core.app.common import OperationType
from chafan_core.app.recs import matrices as recs_matrices
from chafan_core.app.responders import misc as misc_responder
from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.user_permission import user_in_site
from chafan_core.utils.base import EntityType, HTTPException_, filter_not_none, unwrap

MAX_SAMPLED_RELATED_FOLLOWED = 20


def get_user_follows(
    cached_layer, followed: models.User
) -> schemas.UserFollows:
    current_user = cached_layer.try_get_current_user()
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


def preview_of_user(cached_layer, user: models.User) -> schemas.UserPreview:
    """User preview with social annotations for the current principal."""
    from chafan_core.app.responders import user as user_responder

    user_preview = user_responder.plain_preview_of_user(user)
    principal_id = cached_layer.principal_id
    if principal_id:
        m = cached_layer.get_follow_follow_fanout()
        if principal_id in m and user_preview.uuid in m[principal_id]:
            user_preview.social_annotations.follow_follows = m[principal_id][
                user_preview.uuid
            ]
        else:
            user_preview.social_annotations.follow_follows = 0
    user_preview.follows = get_user_follows(cached_layer, user)
    return user_preview


def get_followers(
    cached_layer, user: models.User, skip: int, limit: int
) -> List[UserPreview]:
    return [
        preview_of_user(cached_layer, u) for u in user.followers[skip : skip + limit]
    ]


def get_followed(
    cached_layer, user: models.User, skip: int, limit: int
) -> List[UserPreview]:
    return [
        preview_of_user(cached_layer, u) for u in user.followed[skip : skip + limit]
    ]


def get_authored_answers_for_principal(
    cached_layer, author: models.User
) -> List[schemas.AnswerPreview]:
    mat = cached_layer.materializer
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
    mat = ctx.materializer
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


def list_user_questions(
    ctx, *, uuid: str, skip: int, limit: int
) -> List[schemas.QuestionPreview]:
    user = _require_user(ctx, uuid)
    mat = ctx.materializer
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
    mat = ctx.materializer
    # TODO we have limit, but we still generate all articles. Need generator 2025-Mar-23
    return filter_not_none(
        [mat.preview_of_article(article) for article in user.articles]
    )[skip : skip + limit]


def get_related_users(cached_layer, target_user: models.User) -> List[UserPreview]:
    db = cached_layer.get_db()
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

    return [preview_of_user(cached_layer, u) for u in related_users.values()]
