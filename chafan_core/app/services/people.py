"""People / social graph service."""

from __future__ import annotations

import random
from typing import Dict, List

from chafan_core.app import crud, models, schemas
from chafan_core.app.recs import matrices as recs_matrices
from chafan_core.app.schemas.preview import UserPreview
from chafan_core.utils.base import EntityType, filter_not_none, unwrap

MAX_SAMPLED_RELATED_FOLLOWED = 20


def get_followers(cached_layer, user: models.User, skip: int, limit: int) -> List[UserPreview]:
    return [
        cached_layer.preview_of_user(u) for u in user.followers[skip : skip + limit]
    ]


def get_followed(cached_layer, user: models.User, skip: int, limit: int) -> List[UserPreview]:
    return [
        cached_layer.preview_of_user(u) for u in user.followed[skip : skip + limit]
    ]


def get_authored_answers_for_principal(
    cached_layer, author: models.User
) -> List[schemas.AnswerPreview]:
    return filter_not_none(
        [
            cached_layer.materializer.preview_of_answer(answer)
            for answer in author.answers
        ]
    )


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

    return [cached_layer.preview_of_user(u) for u in related_users.values()]
