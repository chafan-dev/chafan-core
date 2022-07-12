import datetime
import json
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from pydantic.tools import parse_raw_as

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.common import get_redis_cli, is_dev
from chafan_core.app.reactions import add_reaction, cancel_reaction, get_reactions
from chafan_core.app.schemas.reaction import ReactionObjectType

router = APIRouter()


@router.get("/{object_type}/{object_uuid}", response_model=schemas.Reactions)
def get_object_reactions(
    *,
    object_type: ReactionObjectType,
    object_uuid: str,
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    redis = get_redis_cli()
    key = f"chafan:reactions:{object_type}:{object_uuid}:{current_user_id}"
    value = redis.get(key)
    if value is not None:
        return parse_raw_as(schemas.Reactions, value)
    data = _get_object_reactions(
        object_type, object_uuid, current_user_id=current_user_id
    )
    if not is_dev():
        redis.delete(key)
        redis.set(
            key, json.dumps(jsonable_encoder(data)), ex=datetime.timedelta(minutes=30)
        )
    return data


def _get_object_reactions(
    object_type: ReactionObjectType,
    object_uuid: str,
    *,
    current_user_id: Optional[int],
) -> schemas.Reactions:
    counters = get_reactions(object_uuid=object_uuid, object_type=object_type)
    return schemas.Reactions(
        counters={
            reaction: len(users)
            for reaction, users in counters.items()
            if len(users) > 0
        },
        my_reactions=set(
            reaction for reaction, users in counters.items() if current_user_id in users
        ),
    )


@router.put("/", response_model=schemas.Reactions)
def update_object_reaction(
    *,
    reaction_in: schemas.Reaction,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    if reaction_in.action == "add":
        add_reaction(reacton_in=reaction_in, user_id=current_user_id)
    else:
        cancel_reaction(reacton_in=reaction_in, user_id=current_user_id)
    key = f"chafan:reactions:{reaction_in.object_type}:{reaction_in.object_uuid}:{current_user_id}"
    redis = get_redis_cli()
    redis.delete(key)
    data = _get_object_reactions(
        reaction_in.object_type,
        reaction_in.object_uuid,
        current_user_id=current_user_id,
    )
    if not is_dev():
        redis.set(
            key, json.dumps(jsonable_encoder(data)), ex=datetime.timedelta(minutes=30)
        )
    return data
