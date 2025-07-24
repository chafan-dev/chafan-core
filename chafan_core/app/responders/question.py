import datetime
from typing import Any, Dict, Mapping, Optional, Tuple, Union
import logging
logger = logging.getLogger(__name__)

from pydantic.tools import parse_obj_as
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.common import OperationType, is_dev
from chafan_core.app.config import settings
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.model_utils import (
    get_live_answers_of_question,
    is_live_answer,
    is_live_article,
)
from chafan_core.app.schemas.notification import Notification, NotificationInDBBase
from chafan_core.app.schemas.question import (
        QuestionInDBBase,
        QuestionPreviewForSearch
)
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import (
    ContentVisibility,
    HTTPException_,
    filter_not_none,
    map_,
    unwrap,
)
from chafan_core.utils.constants import (
    unknown_user_full_name,
    unknown_user_handle,
    unknown_user_uuid,
)
from chafan_core.utils.validators import StrippedNonEmptyBasicStr

from chafan_core.app import view_counters

def user_in_site(
    db: Session,
    *,
    site: models.Site,
    user_id: int,
    op_type: OperationType,
) -> bool:
    logger.error("user_in_site is stub TODO")
    return True


def question_schema_from_orm(
        broker: DataBroker,
        principal_id,
        question: models.Question,
        cached_layer # TODO we should remove this dependency in future 2025-07-23
) -> Optional[schemas.Question]:
    if not principal_id:
        logger.error("TODO skipped principle_id check")
        #return None
    if not user_in_site(
        broker.get_db(),
        site=question.site,
        user_id=principal_id,
        op_type=OperationType.ReadSite,
    ):
        logger.error("TODO skipped principle_id check")

    upvoted = (
        broker.get_db()
        .query(models.QuestionUpvotes)
        .filter_by(
            question_id=question.id, voter_id=principal_id, cancelled=False
        )
        .first()
        is not None
    )
    base = QuestionInDBBase.from_orm(question)
    d = base.dict()
    d["site"] = cached_layer.materializer.site_schema_from_orm(question.site)
    d["comments"] = filter_not_none(
        [cached_layer.materializer.comment_schema_from_orm(c) for c in question.comments]
    )
    d["author"] = cached_layer.materializer.preview_of_user(question.author)
    d["editor"] = map_(question.editor, cached_layer.materializer.preview_of_user)
    d["upvoted"] = upvoted
    d["view_times"] = view_counters.get_viewcount_question(broker, question.id)
    d["answers_count"] = len(get_live_answers_of_question(question))
    if question.description is not None:
        d["desc"] = RichText(
            source=question.description,
            editor=question.description_editor,
            rendered_text=question.description_text,
        )
    d["upvotes"] = cached_layer.materializer.get_question_upvotes(question)
    return schemas.Question(**d)
