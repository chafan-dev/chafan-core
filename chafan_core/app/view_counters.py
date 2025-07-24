from typing import Literal

import logging
logger = logging.getLogger(__name__)

from chafan_core.app import models
from chafan_core.db.base_class import Base
#from chafan_core.app.cached_layer import CachedLayer



async def add_view_async(
    cached_layer, # TODO 2025-07-20 due to cyclic dep, turn off this type hint: CachedLayer,
    object_type: Literal["question", "answer", "profile", "article", "submission"],
    obj_id: int
) -> None:

    if object_type in ["question", "answer"]:
        cached_layer.bump_view(object_type, obj_id)

    return


def add_view(
    object_uuid: str,
    object_type: Literal["question", "answer", "profile", "article", "submission"],
    user_id: int,
) -> int:
    logger.error("add_view is a deprecated function")
    return 0


from chafan_core.app.models.viewcount import ViewCountQuestion

def get_viewcount_question(broker, row_id:int)->int:
    db = broker.get_db()
    row = db.query(ViewCountQuestion).filter(ViewCountQuestion.question_id == row_id).first()
    if row is None:
        return 0
    return row.view_count
#object_type: Literal["question", "answer", "profile", "article", "submission"],
