from typing import Any, List, Optional, Union

import logging
logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas, view_counters
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import OperationType, client_ip, run_dramatiq_task
from chafan_core.app.endpoint_utils import check_writing_session
from chafan_core.app.limiter import limiter
from chafan_core.app.materialize import (
    answer_archive_schema_from_orm,
    check_user_in_site,
)
from chafan_core.app.schemas.answer import AnswerModUpdate
from chafan_core.app.schemas.event import EventInternal, UpvoteAnswerInternal
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import HTTPException_, filter_not_none, get_utc_now, unwrap
from chafan_core.utils.constants import MAX_ARCHIVE_PAGINATION_LIMIT
from chafan_core.app.task import postprocess_new_answer

router = APIRouter()


@router.get("/{uuid}", response_model=Union[schemas.Answer, schemas.AnswerForVisitor])
def get_one(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    uuid: str,
) -> Any:
    """
    Get answer in one of current_user's belonging sites.
    """
    answer_data = cached_layer.get_answer(uuid)
    if answer_data is None:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    return answer_data


@router.delete("/{uuid}", response_model=schemas.GenericResponse)
def delete_answer(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
) -> Any:
    error_msg = cached_layer.delete_answer(uuid)
    if error_msg:
        raise HTTPException_(
            status_code=400,
            detail="Delete answer failed.",
        )
    return schemas.GenericResponse()


@router.get("/{uuid}/draft", response_model=schemas.answer.AnswerDraft)
def get_answer_draft(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    """
    Get answer's draft body as its author.
    """
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exists in the system.",
        )
    if current_user_id != answer.author_id:
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


@router.delete("/{uuid}/draft", response_model=schemas.answer.AnswerDraft)
def delete_answer_draft(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exists in the system.",
        )
    if current_user_id != answer.author_id:
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


@router.get("/{uuid}/archives/", response_model=List[schemas.AnswerArchive])
def get_answer_archives(
    *,
    db: Session = Depends(deps.get_read_db),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_ARCHIVE_PAGINATION_LIMIT, le=MAX_ARCHIVE_PAGINATION_LIMIT, gt=0
    ),
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    """
    Get answer's archives as its author.
    """
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exists in the system.",
        )
    if current_user_id != answer.author_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    return [
        answer_archive_schema_from_orm(a)
        for a in answer.archives[skip : (skip + limit)]
    ]


@router.post("/{uuid}/views/", response_model=schemas.GenericResponse)
@limiter.limit("60/minute")
def bump_views_counter(
    response: Response,
    request: Request,
    *,
    uuid: str,
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    if current_user_id:
        view_counters.add_view(uuid, "answer", current_user_id)
    return schemas.GenericResponse()


@router.post("/", response_model=schemas.Answer)
def create_answer(
    request: Request,
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    answer_in: schemas.AnswerCreate,
) -> Any:
    """
    Create new answer authored by the current user in one of the belonging sites.
    """
    current_user_id = cached_layer.unwrapped_principal_id()
    crud.audit_log.create_with_user(
        cached_layer.get_db(),
        ipaddr=client_ip(request),
        user_id=current_user_id,
        api="post answer",
        request_info={"answer_in": jsonable_encoder(answer_in)},
    )

    question = crud.question.get_by_uuid(
        cached_layer.get_db(), uuid=answer_in.question_uuid
    )
    if not question:
        raise HTTPException_(
            status_code=400,
            detail="The question doesn't exists in the system.",
        )
    check_writing_session(answer_in.writing_session_uuid)
    check_user_in_site(
        cached_layer.get_db(),
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
        cached_layer.get_db(),
        obj_in=answer_in,
        author_id=current_user_id,
        site_id=question.site_id,
    )
    if answer.is_published:
        logger.info(f"create_answer add postprocess task id={answer.id}")
        run_dramatiq_task(postprocess_new_answer, answer.id, False)
    return cached_layer.materializer.answer_schema_from_orm(answer)


def _update_answer(
    cached_layer: CachedLayer,
    *,
    answer: models.Answer,
    answer_in: schemas.AnswerUpdate,
) -> schemas.Answer:
    db = cached_layer.get_db()
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

    if answer.is_published:
        # NOTE: Since is_published will not be reverted, thus this should only be delivered once
        # TODO: Implement the update subscription logic

        run_dramatiq_task(postprocess_new_answer, answer.id, was_published)

    cached_layer.invalidate_answer_cache(answer.uuid)
    return unwrap(cached_layer.materializer.answer_schema_from_orm(answer))


@router.put("/{uuid}", response_model=schemas.Answer)
def update_answer(
    request: Request,
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
    answer_in: schemas.AnswerUpdate,
) -> Any:
    """
    Update answer authored by current user in one of current user's belonging sites.
    """
    db = cached_layer.get_db()
    current_user_id = cached_layer.unwrapped_principal_id()
    crud.audit_log.create_with_user(
        db,
        ipaddr=client_ip(request),
        user_id=current_user_id,
        api="post answer",
        request_info={"answer_in": jsonable_encoder(answer_in), "uuid": uuid},
    )
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exists in the system.",
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
            detail="The question doesn't exists in the system.",
        )
    check_user_in_site(
        db,
        site=question.site,
        user_id=current_user_id,
        op_type=OperationType.WriteSiteAnswer,
    )
    return _update_answer(cached_layer, answer=answer, answer_in=answer_in)


@router.put("/{uuid}/mod", response_model=schemas.Answer, include_in_schema=False)
def update_answer_by_mod(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
    update_in: AnswerModUpdate,
) -> Any:
    """
    Update answer as moderator of the site.
    """
    db = cached_layer.get_db()
    current_user_id = cached_layer.principal_id
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exists in the system.",
        )
    answer_data = cached_layer.materializer.answer_schema_from_orm(answer)
    if answer_data is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exists in the system.",
        )
    site = crud.site.get_by_id(db, id=answer.site_id)
    if not site:
        # The site doesn't exists in the system.
        return False
    if site.moderator_id != current_user_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    answer = crud.answer.update_checked(
        db, db_obj=answer, obj_in=update_in.dict(exclude_none=True)
    )
    answer_data = cached_layer.materializer.answer_schema_from_orm(answer)
    cached_layer.invalidate_answer_cache(uuid=uuid)
    return answer_data


@router.get("/{uuid}/upvotes/", response_model=schemas.AnswerUpvotes)
def get_answer_upvotes(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    uuid: str,
) -> Any:
    data = cached_layer.get_answer_upvotes(uuid)
    if data is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exists in the system.",
        )
    return data


@router.post("/{uuid}/upvotes/", response_model=schemas.AnswerUpvotes)
def upvote_answer(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Upvote answer as the current user in one of current user's belonging sites.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exists in the system.",
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
                detail="Insuffient coins.",
            )
        question = crud.question.get_by_id(db, id=answer.question_id)
        if not question:
            raise HTTPException_(
                status_code=400,
                detail="The question doesn't exists in the system.",
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
                cached_layer.broker,
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
    cached_layer.invalidate_answer_upvotes_cache(answer.uuid)
    return schemas.AnswerUpvotes(
        answer_uuid=answer.uuid, count=valid_upvotes, upvoted=True
    )


@router.delete("/{uuid}/upvotes/", response_model=schemas.AnswerUpvotes)
def cancel_upvote_answer(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Cancel upvote for answer as the current user in one of current user's belonging sites.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exists in the system.",
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
                detail="The question doesn't exists in the system.",
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
    cached_layer.invalidate_answer_upvotes_cache(answer.uuid)
    return schemas.AnswerUpvotes(
        answer_uuid=answer.uuid, count=valid_upvotes, upvoted=False
    )


@router.get("/{uuid}/suggestions/", response_model=List[schemas.AnswerSuggestEdit])
def get_suggestions(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
) -> Any:
    answer = crud.answer.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if answer is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exists in the system.",
        )
    check_user_in_site(
        cached_layer.get_db(),
        site=answer.site,
        user_id=cached_layer.unwrapped_principal_id(),
        op_type=OperationType.ReadSite,
    )
    return filter_not_none(
        [
            cached_layer.materializer.answer_suggest_edit_schema_from_orm(s)
            for s in answer.suggest_edits
        ]
    )
