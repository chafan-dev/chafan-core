from typing import Any, Dict, Mapping, Optional, Tuple, Union

from chafan_core.app import models, schemas
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import (
    filter_not_none,
)

from chafan_core.app import view_counters


from chafan_core.app.schemas.answer import AnswerInDBBase

import logging

logger = logging.getLogger(__name__)


def answer_schema_from_orm(
    cached_layer, answer: models.Answer, principal_id
) -> Optional[schemas.Answer]:
    db = cached_layer.broker.get_db()
    # if not can_read_answer(db, answer=answer, principal_id=self.principal_id):
    #    return None
    upvoted = (
        db.query(models.Answer_Upvotes)
        .filter_by(answer_id=answer.id, voter_id=principal_id, cancelled=False)
        .first()
        is not None
    )
    # TODO skipped the permission check
    #    comment_writable = user_in_site(
    #        db,
    #        site=answer.site,
    #        user_id=self.principal_id,
    #        op_type=OperationType.WriteSiteComment,
    #    )
    base = AnswerInDBBase.from_orm(answer)
    d = base.dict()
    d["site"] = cached_layer.site_schema_from_orm(answer.site)
    d["comments"] = filter_not_none(
        [cached_layer.materializer.comment_schema_from_orm(c) for c in answer.comments]
    )
    d["author"] = cached_layer.materializer.preview_of_user(answer.author)
    d["question"] = cached_layer.materializer.preview_of_question(answer.question)
    d["upvoted"] = upvoted
    d["comment_writable"] = True  # comment_writable
    d["bookmark_count"] = answer.bookmarkers.count()
    d["archives_count"] = len(answer.archives)
    # principal = crud.user.get(db, id=principal_id)
    # assert principal is not None
    d["bookmarked"] = True  # answer in principal.bookmarked_answers
    d["view_times"] = view_counters.get_viewcount_answer(cached_layer.broker, answer.id)
    if answer.is_published:
        body = answer.body
    else:
        logger.error("FIXME draft read permission not checked")
        if answer.body_draft:
            body = answer.body_draft
        else:
            body = answer.body
    d["content"] = RichText(
        source=body,
        rendered_text=answer.body_prerendered_text,
        editor=answer.editor,
    )
    d["suggest_editable"] = answer.body_draft is None
    return schemas.Answer(**d)
