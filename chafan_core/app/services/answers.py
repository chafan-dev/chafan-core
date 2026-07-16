"""Answer domain service."""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.common import OperationType
from chafan_core.app.endpoint_utils import check_writing_session
from chafan_core.app.schemas.answer import AnswerModUpdate
from chafan_core.app.schemas.event import EventInternal, UpvoteAnswerInternal
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.user_permission import check_user_in_site
from chafan_core.utils.base import HTTPException_, get_utc_now, unwrap
from chafan_core.utils.constants import MAX_ARCHIVE_PAGINATION_LIMIT
import chafan_core.app.responders as responders

logger = logging.getLogger(__name__)


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


def get_answer_by_uuid(db: Session, uuid: str) -> Optional[models.Answer]:
    return crud.answer.get_by_uuid(db, uuid=uuid)


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


def get_draft(
    db: Session, *, uuid: str, principal_id: int
) -> schemas.answer.AnswerDraft:
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exist in the system.",
        )
    if principal_id != answer.author_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    draft = None
    if answer.body_draft:
        draft = RichText(source=answer.body_draft, editor=answer.draft_editor)
    return schemas.answer.AnswerDraft(
        draft_saved_at=answer.draft_saved_at,
        content_draft=draft,
    )


def delete_draft(
    db: Session, *, uuid: str, principal_id: int
) -> schemas.answer.AnswerDraft:
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exist in the system.",
        )
    if principal_id != answer.author_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    if not answer.body_draft:
        raise HTTPException_(
            status_code=400,
            detail="Answer has no draft.",
        )
    data = schemas.answer.AnswerDraft(
        draft_saved_at=answer.draft_saved_at,
        content_draft=RichText(
            source=answer.body_draft,
            editor=answer.draft_editor,
        ),
    )
    answer.body_draft = None
    answer.draft_saved_at = None
    db.add(answer)
    db.commit()
    return data


def list_archives(
    db: Session,
    *,
    uuid: str,
    principal_id: int,
    skip: int = 0,
    limit: int = MAX_ARCHIVE_PAGINATION_LIMIT,
) -> List[schemas.AnswerArchive]:
    from chafan_core.app.responders.archives import answer_archive_schema_from_orm

    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exist in the system.",
        )
    if principal_id != answer.author_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    return [
        answer_archive_schema_from_orm(a)
        for a in answer.archives[skip : (skip + limit)]
    ]


def bump_views(ctx, *, uuid: str) -> None:
    from chafan_core.app import view_counters

    answer = crud.answer.get_by_uuid(ctx.get_db(), uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exist in the system.",
        )
    view_counters.add_view_async(ctx, "answer", answer.id)


def create_answer(
    ctx,
    *,
    answer_in: schemas.AnswerCreate,
    ipaddr: Optional[str] = None,
) -> Tuple[models.Answer, schemas.Answer, bool]:
    """Create answer. Returns (answer, schema, needs_postprocess)."""
    current_user_id = ctx.unwrapped_principal_id()
    db = ctx.get_db()
    if ipaddr is not None:
        crud.audit_log.create_with_user(
            db,
            ipaddr=ipaddr,
            user_id=current_user_id,
            api="post answer",
            request_info={"answer_in": jsonable_encoder(answer_in)},
        )

    question = crud.question.get_by_uuid(db, uuid=answer_in.question_uuid)
    if not question:
        raise HTTPException_(
            status_code=400,
            detail="The question doesn't exist in the system.",
        )
    check_writing_session(answer_in.writing_session_uuid)
    check_user_in_site(
        db,
        site=question.site,
        user_id=current_user_id,
        op_type=OperationType.WriteSiteAnswer,
    )
    if any(
        answer.author_id == current_user_id
        for answer in question.answers
        if not answer.is_deleted
    ):
        raise HTTPException_(
            status_code=400,
            detail="You have saved an answer before.",
        )
    answer = crud.answer.create_with_author(
        db,
        obj_in=answer_in,
        author_id=current_user_id,
        site_id=question.site_id,
    )
    data = answer_schema(ctx, answer)
    assert data is not None
    return answer, data, bool(answer.is_published)


def update_answer(
    ctx,
    *,
    uuid: str,
    answer_in: schemas.AnswerUpdate,
    ipaddr: Optional[str] = None,
) -> Tuple[models.Answer, schemas.Answer, bool, bool]:
    """Update answer. Returns (answer, schema, needs_postprocess, was_published)."""
    db = ctx.get_db()
    current_user_id = ctx.unwrapped_principal_id()
    if ipaddr is not None:
        crud.audit_log.create_with_user(
            db,
            ipaddr=ipaddr,
            user_id=current_user_id,
            api="post answer",
            request_info={"answer_in": jsonable_encoder(answer_in), "uuid": uuid},
        )
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exist in the system.",
        )
    if answer.author_id != current_user_id:
        raise HTTPException_(
            status_code=400,
            detail="The answer is not authored by current user.",
        )
    question = crud.question.get_by_id(db, id=answer.question_id)
    if not question:
        raise HTTPException_(
            status_code=400,
            detail="The question doesn't exist in the system.",
        )
    check_user_in_site(
        db,
        site=question.site,
        user_id=current_user_id,
        op_type=OperationType.WriteSiteAnswer,
    )
    answer, data, needs_postprocess, was_published = apply_answer_update(
        ctx, answer=answer, answer_in=answer_in
    )
    return answer, data, needs_postprocess, was_published


def apply_answer_update(
    ctx,
    *,
    answer: models.Answer,
    answer_in: schemas.AnswerUpdate,
) -> Tuple[models.Answer, schemas.Answer, bool, bool]:
    """Apply update to an existing answer model (used by suggest-edit accept)."""
    db = ctx.get_db()
    answer_in_dict = answer_in.dict(exclude_none=True)
    if answer_in.is_draft and answer_in.updated_content:
        del answer_in_dict["updated_content"]
        answer_in_dict["body_draft"] = answer_in.updated_content.source
        answer_in_dict["draft_editor"] = answer_in.updated_content.editor
        answer_in_dict["draft_saved_at"] = get_utc_now()
    else:
        if answer.is_published:
            archive = models.Archive(
                editor=answer.editor,
                answer_id=answer.id,
                body=answer.body,
                created_at=answer.updated_at,
            )
            db.add(archive)
            answer.archives.append(archive)
            db.commit()
        answer_in_dict["is_published"] = True
        answer_in_dict["updated_at"] = get_utc_now()

        if answer_in.updated_content:
            del answer_in_dict["updated_content"]
            answer_in_dict["body"] = answer_in.updated_content.source
            answer_in_dict[
                "body_prerendered_text"
            ] = answer_in.updated_content.rendered_text
            answer_in_dict["editor"] = answer_in.updated_content.editor

        answer_in_dict["body_draft"] = None
        answer_in_dict["draft_saved_at"] = None

    was_published = answer.is_published
    answer = crud.answer.update_checked(db, db_obj=answer, obj_in=answer_in_dict)
    data = unwrap(answer_schema(ctx, answer))
    needs_postprocess = bool(answer.is_published)
    return answer, data, needs_postprocess, was_published


def update_answer_by_mod(
    ctx, *, uuid: str, update_in: AnswerModUpdate
) -> schemas.Answer:
    db = ctx.get_db()
    current_user_id = ctx.principal_id
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exist in the system.",
        )
    answer_data = answer_schema(ctx, answer)
    if answer_data is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exist in the system.",
        )
    site = crud.site.get_by_id(db, id=answer.site_id)
    if not site:
        # The site doesn't exist in the system.
        return False  # type: ignore[return-value]
    if site.moderator_id != current_user_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    answer = crud.answer.update_checked(
        db, db_obj=answer, obj_in=update_in.dict(exclude_none=True)
    )
    answer_data = answer_schema(ctx, answer)
    return answer_data


def upvote_answer(ctx, *, uuid: str) -> schemas.AnswerUpvotes:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exist in the system.",
        )
    upvoted = (
        db.query(models.Answer_Upvotes)
        .filter_by(answer_id=answer.id, voter_id=current_user.id, cancelled=False)
        .first()
        is not None
    )
    if not upvoted:
        if current_user.id == answer.author_id:
            raise HTTPException_(
                status_code=400,
                detail="Author can't upvote authored answer.",
            )
        if current_user.remaining_coins < answer.site.upvote_answer_coin_deduction:
            raise HTTPException_(
                status_code=400,
                detail="Insufficient coins.",
            )
        question = crud.question.get_by_id(db, id=answer.question_id)
        if not question:
            raise HTTPException_(
                status_code=400,
                detail="The question doesn't exist in the system.",
            )
        check_user_in_site(
            db,
            site=question.site,
            user_id=current_user.id,
            op_type=OperationType.ReadSite,
        )
        upvoted_before = (
            db.query(models.Answer_Upvotes)
            .filter_by(answer_id=answer.id, voter_id=current_user.id)
            .first()
            is not None
        )
        # Don't swap the statements before and after!
        answer = crud.answer.upvote(db, db_obj=answer, voter=current_user)
        if not upvoted_before:
            crud.coin_payment.make_payment(
                db,
                obj_in=schemas.CoinPaymentCreate(
                    payee_id=answer.author_id,
                    amount=answer.site.upvote_answer_coin_deduction,
                    event_json=EventInternal(
                        created_at=get_utc_now(),
                        content=UpvoteAnswerInternal(
                            subject_id=current_user.id,
                            answer_id=answer.id,
                        ),
                    ).json(),
                ),
                payer=current_user,
                payee=answer.author,
            )
            crud.notification.create_with_content(
                ctx,
                receiver_id=answer.author.id,
                event=EventInternal(
                    created_at=get_utc_now(),
                    content=UpvoteAnswerInternal(
                        subject_id=current_user.id,
                        answer_id=answer.id,
                    ),
                ),
            )
        db.commit()
        db.refresh(answer)
    valid_upvotes = (
        db.query(models.Answer_Upvotes)
        .filter_by(answer_id=answer.id, cancelled=False)
        .count()
    )
    return schemas.AnswerUpvotes(
        answer_uuid=answer.uuid, count=valid_upvotes, upvoted=True
    )


def cancel_upvote_answer(ctx, *, uuid: str) -> schemas.AnswerUpvotes:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exist in the system.",
        )
    upvoted = (
        db.query(models.Answer_Upvotes)
        .filter_by(answer_id=answer.id, voter_id=current_user.id, cancelled=False)
        .first()
        is not None
    )
    if upvoted:
        question = crud.question.get_by_id(db, id=answer.question_id)
        if not question:
            raise HTTPException_(
                status_code=400,
                detail="The question doesn't exist in the system.",
            )
        check_user_in_site(
            db,
            site=question.site,
            user_id=current_user.id,
            op_type=OperationType.ReadSite,
        )
        answer = crud.answer.cancel_upvote(db, db_obj=answer, voter=current_user)
        db.commit()
        db.refresh(answer)
    valid_upvotes = (
        db.query(models.Answer_Upvotes)
        .filter_by(answer_id=answer.id, cancelled=False)
        .count()
    )
    return schemas.AnswerUpvotes(
        answer_uuid=answer.uuid, count=valid_upvotes, upvoted=False
    )


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
