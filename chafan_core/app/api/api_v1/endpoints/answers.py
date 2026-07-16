from typing import Any, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.common import client_ip
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.limiter import limiter
from chafan_core.app.schemas.answer import AnswerModUpdate
from chafan_core.app.services import answers as answers_service
from chafan_core.app.services.postprocess import postprocess_new_answer
from chafan_core.utils.base import HTTPException_
from chafan_core.utils.constants import MAX_ARCHIVE_PAGINATION_LIMIT

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{uuid}", response_model=schemas.Answer)
def get_one(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
) -> Any:
    """
    Get answer in one of current_user's belonging sites.
    """
    answer_data = answers_service.get_answer_schema(ctx, uuid)
    if answer_data is None:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    return answer_data


@router.delete("/{uuid}", response_model=schemas.GenericResponse)
def delete_answer(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
) -> Any:
    error_msg = answers_service.delete_answer(
        ctx.get_db(),
        uuid=uuid,
        principal_id=ctx.principal_id,
    )
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
    return answers_service.get_draft(
        db, uuid=uuid, principal_id=current_user_id
    )


@router.delete("/{uuid}/draft", response_model=schemas.answer.AnswerDraft)
def delete_answer_draft(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    return answers_service.delete_draft(
        db, uuid=uuid, principal_id=current_user_id
    )


@router.get("/{uuid}/archives/", response_model=List[schemas.AnswerArchive])
def get_answer_archives(
    *,
    db: Session = Depends(deps.get_db),
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
    return answers_service.list_archives(
        db, uuid=uuid, principal_id=current_user_id, skip=skip, limit=limit
    )


@router.post("/{uuid}/views/", response_model=schemas.GenericResponse)
@limiter.limit("60/minute")
def bump_views_counter(
    response: Response,
    request: Request,
    *,
    uuid: str,
    ctx: RequestContext = Depends(deps.get_request_context),
) -> Any:
    answers_service.bump_views(ctx, uuid=uuid)
    return schemas.GenericResponse()


@router.post("/", response_model=schemas.Answer)
def create_answer(
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    answer_in: schemas.AnswerCreate,
    background_tasks: BackgroundTasks,
) -> Any:
    """
    Create new answer authored by the current user in one of the belonging sites.
    """
    answer, data, needs_postprocess = answers_service.create_answer(
        ctx, answer_in=answer_in, ipaddr=client_ip(request)
    )
    if needs_postprocess:
        logger.info(f"create_answer add postprocess task id={answer.id}")
        background_tasks.add_task(postprocess_new_answer, answer.id, False)
    return data


@router.put("/{uuid}", response_model=schemas.Answer)
def update_answer(
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
    answer_in: schemas.AnswerUpdate,
    background_tasks: BackgroundTasks,
) -> Any:
    """
    Update answer authored by current user in one of current user's belonging sites.
    """
    answer, data, needs_postprocess, was_published = answers_service.update_answer(
        ctx, uuid=uuid, answer_in=answer_in, ipaddr=client_ip(request)
    )
    if needs_postprocess:
        background_tasks.add_task(postprocess_new_answer, answer.id, was_published)
    return data


@router.put("/{uuid}/mod", response_model=schemas.Answer, include_in_schema=False)
def update_answer_by_mod(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
    update_in: AnswerModUpdate,
) -> Any:
    """
    Update answer as moderator of the site.
    """
    return answers_service.update_answer_by_mod(
        ctx, uuid=uuid, update_in=update_in
    )


@router.get("/{uuid}/upvotes/", response_model=schemas.AnswerUpvotes)
def get_answer_upvotes(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
) -> Any:
    data = answers_service.get_answer_upvotes(
        ctx.get_db(),
        uuid=uuid,
        principal_id=ctx.principal_id,
    )
    if data is None:
        raise HTTPException_(
            status_code=400,
            detail="The answer doesn't exist in the system.",
        )
    return data


@router.post("/{uuid}/upvotes/", response_model=schemas.AnswerUpvotes)
def upvote_answer(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Upvote answer as the current user in one of current user's belonging sites.
    """
    return answers_service.upvote_answer(ctx, uuid=uuid)


@router.delete("/{uuid}/upvotes/", response_model=schemas.AnswerUpvotes)
def cancel_upvote_answer(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Cancel upvote for answer as the current user in one of current user's belonging sites.
    """
    return answers_service.cancel_upvote_answer(ctx, uuid=uuid)


@router.get("/{uuid}/suggestions/", response_model=List[schemas.AnswerSuggestEdit])
def get_suggestions(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
) -> Any:
    return answers_service.list_suggest_edits(ctx, uuid=uuid)
