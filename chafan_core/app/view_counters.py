from typing import Literal



async def add_view_async(
    object_uuid: str,
    object_type: Literal["question", "answer", "profile", "article", "submission"],
    user_id: int,
) -> int:
    return 0
    return add_view(object_uuid, object_type, user_id)


def add_view(
    object_uuid: str,
    object_type: Literal["question", "answer", "profile", "article", "submission"],
    user_id: int,
) -> int:
    return 0


# TODO: caching strategy?
def get_views(
    object_uuid: str,
    object_type: Literal["question", "answer", "profile", "article", "submission"],
) -> int:
    return 0
    result = db.views.find_one(
        {
            "object_uuid": object_uuid,
            "object_type": object_type,
        }
    )
    if result is None:
        return 0
    return len(result["counter"])
