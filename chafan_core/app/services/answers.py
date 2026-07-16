"""Answer domain service."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
import chafan_core.app.responders as responders


def delete_answer(
    db: Session, *, uuid: str, principal_id: Optional[int]
) -> Optional[str]:
    """Delete answer forever. Returns error message or None on success."""
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        return "The answer doesn't exist in the system."
    if answer.author_id != principal_id:
        return "Unauthorized."
    crud.answer.delete_forever(db, answer=answer)
    return None


def get_answer_upvotes(
    db: Session, *, uuid: str, principal_id: Optional[int]
) -> Optional[schemas.AnswerUpvotes]:
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        return None
    upvoted = False
    if principal_id:
        upvoted = (
            db.query(models.Answer_Upvotes)
            .filter_by(answer_id=answer.id, voter_id=principal_id, cancelled=False)
            .first()
            is not None
        )
    valid_upvotes = (
        db.query(models.Answer_Upvotes)
        .filter_by(answer_id=answer.id, cancelled=False)
        .count()
    )
    return schemas.AnswerUpvotes(
        answer_uuid=answer.uuid, count=valid_upvotes, upvoted=upvoted
    )


def get_answer_by_id(db: Session, answer_id: int) -> Optional[models.Answer]:
    return crud.answer.get_by_id(db, uid=answer_id)


def answer_schema(ctx, answer: models.Answer) -> Optional[schemas.Answer]:
    answer_data = responders.answer.answer_schema_from_orm(
        ctx, answer, ctx.principal_id
    )
    if answer_data:
        answer_data.upvotes = get_answer_upvotes(
            ctx.get_db(),
            uuid=answer.uuid,
            principal_id=ctx.principal_id,
        )
    return answer_data


def get_answer_schema(ctx, uuid: str) -> Optional[schemas.Answer]:
    """Shape a single answer for the layer principal (permission gated)."""
    db = ctx.get_db()
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        return None
    return answer_schema(ctx, answer)


def list_suggest_edits(ctx, *, uuid: str):
    from chafan_core.app.common import OperationType
    from chafan_core.app.responders import suggestions as suggestions_responder
    from chafan_core.app.user_permission import check_user_in_site
    from chafan_core.utils.base import HTTPException_, filter_not_none

    answer = crud.answer.get_by_uuid(ctx.get_db(), uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exist in the system.",
        )
    check_user_in_site(
        ctx.get_db(),
        site=answer.site,
        user_id=ctx.unwrapped_principal_id(),
        op_type=OperationType.ReadSite,
    )
    mat = ctx.principal_view
    return filter_not_none(
        [
            suggestions_responder.answer_suggest_edit_schema_from_orm(mat, s)
            for s in answer.suggest_edits
        ]
    )
