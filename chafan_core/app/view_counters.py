from typing import Literal

import logging
logger = logging.getLogger(__name__)

from chafan_core.app import models
from chafan_core.db.base_class import Base
#from chafan_core.app.cached_layer import CachedLayer



async def add_view_async(
    cached_layer, # TODO 2025-07-20 due to cyclic dep, turn off this type hint: CachedLayer,
    obj: Base,
    object_type: Literal["question", "answer", "profile", "article", "submission"],
) -> None:
    logger.info(type(obj))

    if isinstance(obj, models.Question):
        assert object_type == "question"
        cached_layer.bump_view(object_type, obj.id)
        return

    return


def add_view(
    object_uuid: str,
    object_type: Literal["question", "answer", "profile", "article", "submission"],
    user_id: int,
) -> int:
    logger.error("add_view is a deprecated function")
    return 0


#object_type: Literal["question", "answer", "profile", "article", "submission"],
