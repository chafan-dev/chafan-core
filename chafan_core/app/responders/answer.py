from typing import Optional, Tuple
import logging

from chafan_core.app import crud, models, schemas, user_permission, view_counters
from chafan_core.app.common import OperationType
from chafan_core.app.responders._util import get_db, shaper
from chafan_core.app.schemas.answer import AnswerInDBBase
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import filter_not_none

logger = logging.getLogger(__name__)

_MAX_ANSWER_BODY_CHARS = 100


def get_answer_text_preview(answer: models.Answer) -> Tuple[str, bool]:
    text = answer.body_prerendered_text or ""
    if len(text) > _MAX_ANSWER_BODY_CHARS:
        return text[:_MAX_ANSWER_BODY_CHARS] + "...", True
    return text, False


def answer_preview_base(mat, answer: models.Answer) -> schemas.answer.AnswerPreviewBase:
    preview_body, truncated = get_answer_text_preview(answer)
    return schemas.answer.AnswerPreviewBase(
        uuid=answer.uuid,
        body=preview_body,
        body_is_truncated=truncated,
        author=mat.preview_of_user(answer.author),
        upvotes_count=answer.upvotes_count,
        is_hidden_by_moderator=answer.is_hidden_by_moderator,
        featured_at=answer.featured_at,
    )


def preview_of_answer(ctx, answer: models.Answer) -> Optional[schemas.AnswerPreview]:
    """One answer preview for any principal allowed to read the answer."""
    from chafan_core.app.responders import question as question_responder

    db = get_db(ctx)
    principal_id = ctx.principal_id
    if not user_permission.answer_read_allowed(db, answer=answer, user_id=principal_id):
        return None
    mat = shaper(ctx)
    question = question_responder.preview_of_question(mat, answer.question)
    if question is None:
        return None
    base = answer_preview_base(mat, answer)
    return schemas.AnswerPreview(
        **base.dict(),
        question=question,
        full_answer=None,
    )


def answer_schema_from_orm(
    ctx, answer: models.Answer, principal_id
) -> Optional[schemas.Answer]:
    db = get_db(ctx)
    if not user_permission.answer_read_allowed(db, answer=answer, user_id=principal_id):
        return None

    upvoted = False
    comment_writable = False
    bookmarked = False
    if principal_id is not None:
        upvoted = (
            db.query(models.Answer_Upvotes)
            .filter_by(answer_id=answer.id, voter_id=principal_id, cancelled=False)
            .first()
            is not None
        )
        comment_writable = user_permission.user_in_site(
            db,
            site=answer.site,
            user_id=principal_id,
            op_type=OperationType.WriteSiteComment,
        )
        principal = crud.user.get(db, id=principal_id)
        if principal is not None:
            bookmarked = answer in principal.bookmarked_answers

    mat = shaper(ctx)
    base = AnswerInDBBase.from_orm(answer)
    d = base.dict()
    d["site"] = ctx.site_schema_from_orm(answer.site)
    d["comments"] = filter_not_none(
        [mat.comment_schema_from_orm(c) for c in answer.comments]
    )
    d["author"] = mat.preview_of_user(answer.author)
    d["question"] = mat.preview_of_question(answer.question)
    d["upvoted"] = upvoted
    d["comment_writable"] = comment_writable
    d["bookmark_count"] = answer.bookmarkers.count()
    d["archives_count"] = len(answer.archives)
    d["bookmarked"] = bookmarked
    d["view_times"] = view_counters.get_viewcount_answer(ctx, answer.id)

    if answer.is_published:
        body = answer.body
    else:
        # Unpublished drafts: only the author may read (enforced above); serve draft body.
        if principal_id != answer.author_id:
            return None
        body = answer.body_draft if answer.body_draft else answer.body

    d["content"] = RichText(
        source=body,
        rendered_text=answer.body_prerendered_text,
        editor=answer.editor,
    )
    d["suggest_editable"] = answer.body_draft is None
    return schemas.Answer(**d)
