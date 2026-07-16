"""Answer suggest-edit domain service."""

from __future__ import annotations

from typing import Tuple

import sentry_sdk
from fastapi.encoders import jsonable_encoder

from chafan_core.app import crud, models, schemas
from chafan_core.app.common import OperationType
from chafan_core.app.responders import suggestions as suggestions_responder
from chafan_core.app.schemas.answer import AnswerUpdate
from chafan_core.app.schemas.answer_suggest_edit import (
    AnswerSuggestEditCreate,
    AnswerSuggestEditUpdate,
)
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.services import answers as answers_service
from chafan_core.app.user_permission import check_user_in_site
from chafan_core.utils.base import HTTPException_, get_utc_now, unwrap


def create_suggest_edit(
    ctx, *, create_in: AnswerSuggestEditCreate
) -> Tuple[models.AnswerSuggestEdit, schemas.AnswerSuggestEdit]:
    current_user = ctx.get_current_active_user()
    answer = crud.answer.get_by_uuid(ctx.get_db(), uuid=create_in.answer_uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exist in the system.",
        )
    check_user_in_site(
        ctx.get_db(),
        site=answer.site,
        user_id=current_user.id,
        op_type=OperationType.WriteSiteAnswer,
    )
    if answer.body_draft:
        raise HTTPException_(
            status_code=400,
            detail="The answer has draft with potential conflict.",
        )
    if current_user.remaining_coins < answer.site.create_suggestion_coin_deduction:
        raise HTTPException_(
            status_code=400,
            detail="Insufficient coins.",
        )
    s = crud.answer_suggest_edit.create_with_author(
        ctx.get_db(),
        obj_in=create_in,
        author_id=current_user.id,
        answer=answer,
    )
    data = unwrap(
        suggestions_responder.answer_suggest_edit_schema_from_orm(
            ctx.principal_view, s
        )
    )
    return s, data


def _check_author(answer_suggest_edit: models.AnswerSuggestEdit, user_id: int) -> None:
    if answer_suggest_edit.answer.author_id != user_id:
        raise HTTPException_(
            status_code=400,
            detail="Only author of answer can do this.",
        )


def _check_suggestion_author(
    answer_suggest_edit: models.AnswerSuggestEdit, user_id: int
) -> None:
    if answer_suggest_edit.author_id != user_id:
        raise HTTPException_(
            status_code=400,
            detail="Only author of suggestion can do this.",
        )


def update_suggest_edit(
    ctx, *, uuid: str, update_in: AnswerSuggestEditUpdate
) -> Tuple[
    schemas.AnswerSuggestEdit,
    bool,
    models.AnswerSuggestEdit | None,
    models.Answer | None,
    bool,
    bool,
]:
    """Update suggest-edit status.

    Returns:
        (schema, needs_accept_postprocess, suggest_edit_for_accept,
         updated_answer_if_accepted, answer_needs_postprocess, answer_was_published)
    """
    db = ctx.get_db()
    current_user_id = ctx.unwrapped_principal_id()
    answer_suggest_edit = crud.answer_suggest_edit.get_by_uuid(db, uuid=uuid)
    if answer_suggest_edit is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer_suggest_edit doesn't exist in the system.",
        )
    check_user_in_site(
        db,
        site=answer_suggest_edit.answer.site,
        user_id=current_user_id,
        op_type=OperationType.WriteSiteAnswer,
    )
    utc_now = get_utc_now()
    old_status = answer_suggest_edit.status
    new_status = update_in.status
    update_dict = update_in.dict()
    accepted_answer: models.Answer | None = None
    answer_needs_postprocess = False
    answer_was_published = False
    needs_accept_postprocess = False

    if old_status in ["pending", "rejected"]:
        if new_status == "accepted":
            _check_author(answer_suggest_edit, current_user_id)
            update_dict["accepted_at"] = utc_now
            original_body = None
            if answer_suggest_edit.answer.body:
                original_body = RichText(
                    source=answer_suggest_edit.answer.body,
                    editor=answer_suggest_edit.answer.editor,
                    rendered_text=answer_suggest_edit.answer.body_prerendered_text,
                )
            answer_suggest_edit.accepted_diff_base = jsonable_encoder(
                original_body,
            )
            if (
                answer_suggest_edit.author
                not in answer_suggest_edit.answer.contributors
            ):
                answer_suggest_edit.answer.contributors.append(
                    answer_suggest_edit.author
                )
            db.commit()
            body_rich_text = None
            if answer_suggest_edit.body:
                assert answer_suggest_edit.body_editor
                body_rich_text = RichText(
                    source=answer_suggest_edit.body,
                    rendered_text=answer_suggest_edit.body_text,
                    editor=answer_suggest_edit.body_editor,
                )
            (
                accepted_answer,
                _data,
                answer_needs_postprocess,
                answer_was_published,
            ) = answers_service.apply_answer_update(
                ctx,
                answer=answer_suggest_edit.answer,
                answer_in=AnswerUpdate(
                    updated_content=body_rich_text,
                    is_draft=False,
                    visibility=answer_suggest_edit.answer.visibility,
                ),
            )
            needs_accept_postprocess = True
        elif new_status == "rejected":
            _check_author(answer_suggest_edit, current_user_id)
            update_dict["rejected_at"] = utc_now
        elif new_status == "retracted":
            _check_suggestion_author(answer_suggest_edit, current_user_id)
            update_dict["retracted_at"] = utc_now
        else:
            sentry_sdk.capture_message(f"Unknown answer status: {old_status}")
            raise HTTPException_(
                status_code=400,
                detail=f"Unknown status.",
            )
    elif old_status == "accepted":
        raise HTTPException_(
            status_code=400,
            detail=f"Can't change accepted suggestion.",
        )
    elif old_status == "retracted" and new_status == "pending":
        _check_suggestion_author(answer_suggest_edit, current_user_id)
        update_dict["retracted_at"] = None
    else:
        raise HTTPException_(
            status_code=400,
            detail=f"Unsupported status.",
        )
    s = crud.answer_suggest_edit.update(
        db, db_obj=answer_suggest_edit, obj_in=update_dict
    )
    data = unwrap(
        suggestions_responder.answer_suggest_edit_schema_from_orm(
            ctx.principal_view, s
        )
    )
    return (
        data,
        needs_accept_postprocess,
        s if needs_accept_postprocess else None,
        accepted_answer,
        answer_needs_postprocess,
        answer_was_published,
    )
