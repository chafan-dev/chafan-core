from typing import Mapping, Set

from chafan_core.app.common import get_mongo_db, is_dev
from chafan_core.app.schemas import Reaction
from chafan_core.app.schemas.reaction import ReactionObjectType


def add_reaction(reacton_in: Reaction, user_id: int) -> int:
    if is_dev():
        return 1
    db = get_mongo_db()
    result = db.reactions.update_one(
        {
            "object_uuid": reacton_in.object_uuid,
            "object_type": reacton_in.object_type,
        },
        {"$addToSet": {f"counters.{reacton_in.reaction}": user_id}},
        upsert=True,
    )
    return result.modified_count


def cancel_reaction(reacton_in: Reaction, user_id: int) -> int:
    if is_dev():
        return 1
    db = get_mongo_db()
    result = db.reactions.update_one(
        {
            "object_uuid": reacton_in.object_uuid,
            "object_type": reacton_in.object_type,
        },
        {"$pull": {f"counters.{reacton_in.reaction}": user_id}},
    )
    return result.modified_count


# TODO: caching strategy?
def get_reactions(
    object_uuid: str,
    object_type: ReactionObjectType,
) -> Mapping[str, Set[int]]:
    if is_dev():
        return {"👍": set([0])}
    db = get_mongo_db()
    result = db.reactions.find_one(
        {
            "object_uuid": object_uuid,
            "object_type": object_type,
        }
    )
    if result is None:
        return {}
    return result["counters"]
