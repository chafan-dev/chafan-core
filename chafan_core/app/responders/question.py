from typing import Optional
import logging

logger = logging.getLogger(__name__)

import chafan_core.app.responders as responders
from chafan_core.app import models, schemas
from chafan_core.app.common import OperationType
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.model_utils import (
    get_live_answers_of_question,
)
from chafan_core.app.schemas.question import QuestionInDBBase
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app import user_permission, view_counters
from chafan_core.utils.base import (
    filter_not_none,
    map_,
)


def question_schema_from_orm(
    broker: DataBroker,
    principal_id,
    question: models.Question,
    cached_layer,  # TODO we should remove this dependency in future 2025-07-23
) -> Optional[schemas.Question]:
    db = broker.get_db()
    if not user_permission.user_in_site(
        db,
        site=question.site,
        user_id=principal_id,
        op_type=OperationType.ReadSite,
    ):
        return None

    upvoted = False
    if principal_id is not None:
        upvoted = (
            db.query(models.QuestionUpvotes)
            .filter_by(
                question_id=question.id, voter_id=principal_id, cancelled=False
            )
            .first()
            is not None
        )
    base = QuestionInDBBase.from_orm(question)
    d = base.dict()
    d["site"] = responders.site.site_schema_from_orm(cached_layer, question.site)
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
