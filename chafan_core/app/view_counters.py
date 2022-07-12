from typing import Literal

from chafan_core.app.common import get_mongo_db, is_dev


async def add_view_async(
    object_uuid: str,
    object_type: Literal["question", "answer", "profile", "article", "submission"],
    user_id: int,
) -> int:
    return add_view(object_uuid, object_type, user_id)


def add_view(
    object_uuid: str,
    object_type: Literal["question", "answer", "profile", "article", "submission"],
    user_id: int,
) -> int:
    if is_dev():
        return 0
    db = get_mongo_db()
    result = db.views.update_one(
        {
            "object_uuid": object_uuid,
            "object_type": object_type,
        },
        {"$addToSet": {f"counter": user_id}},
        upsert=True,
    )
    return result.modified_count


# TODO: caching strategy?
def get_views(
    object_uuid: str,
    object_type: Literal["question", "answer", "profile", "article", "submission"],
) -> int:
    if is_dev():
        return 0
    db = get_mongo_db()
    result = db.views.find_one(
        {
            "object_uuid": object_uuid,
            "object_type": object_type,
        }
    )
    if result is None:
        return 0
    return len(result["counter"])
