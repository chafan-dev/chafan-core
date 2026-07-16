from typing import Any, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.common import client_ip
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.limiter import limiter
from chafan_core.app.services import questions as questions_service
from chafan_core.app.services.postprocess import (
    postprocess_new_question,
    postprocess_updated_question,
)

router = APIRouter()


@router.get(
    "/{uuid}", response_model=schemas.Question
)
@limiter.limit("60/minute")
def get_question(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
) -> Any:
    """
    Get question in one of current_user's belonging sites.
    """
    return questions_service.get_question(ctx, uuid=uuid)


@router.post("/{uuid}/views/", response_model=schemas.GenericResponse)
def bump_views_counter(
    *,
    uuid: str,
    ctx: RequestContext = Depends(deps.get_request_context),
    _current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    questions_service.bump_views(ctx, uuid=uuid)
    return schemas.GenericResponse()


@router.get(
    "/{uuid}/answers/",
    response_model=List[schemas.AnswerPreview],
)
def get_question_answers(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    """
    Get question's answers' previews.
    """
    return questions_service.get_question_answers(
        ctx, uuid=uuid, principal_id=current_user_id
    )


@router.post("/", response_model=schemas.Question)
def create_question(
    request: Request,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    question_in: schemas.QuestionCreate,
    background_tasks: BackgroundTasks,
) -> Any:
    """
    Create new question authored by the current user in one of the belonging sites.
    """
    new_question, data = questions_service.create_question(
        ctx, question_in=question_in, ipaddr=client_ip(request)
    )
    background_tasks.add_task(postprocess_new_question, new_question.id)
    return data


@router.put("/{uuid}", response_model=schemas.Question)
def update_question(
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
    question_in: schemas.QuestionUpdate,
    current_user_id: int = Depends(deps.get_current_user_id),
    background_tasks: BackgroundTasks,
) -> Any:
    """
    Update question in one of current_user's belonging sites as member.
    """
    new_question, data = questions_service.update_question(
        ctx,
        uuid=uuid,
        question_in=question_in,
        current_user_id=current_user_id,
        ipaddr=client_ip(request),
    )
    background_tasks.add_task(postprocess_updated_question, new_question.id)
    return data


@router.get("/{uuid}/archives/", response_model=List[schemas.QuestionArchive])
def get_question_archives(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
) -> Any:
    return questions_service.list_archives(ctx, uuid=uuid)


@router.get("/{uuid}/upvotes/", response_model=schemas.QuestionUpvotes)
def get_question_upvotes(
    ctx: RequestContext = Depends(deps.get_request_context),
    *,
    uuid: str,
) -> Any:
    return questions_service.get_upvotes(ctx, uuid=uuid)


@router.put("/{uuid}/hide", response_model=schemas.Question)
def hide_question(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    return questions_service.hide_question(ctx, uuid=uuid)


@router.post(
    "/{uuid}/invite-answer/{user_uuid}", response_model=schemas.GenericResponse
)
def invite_answer(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
    user_uuid: str,
) -> Any:
    questions_service.invite_answer(ctx, uuid=uuid, user_uuid=user_uuid)
    return schemas.GenericResponse()


@router.post("/{uuid}/upvotes/", response_model=schemas.QuestionUpvotes)
def upvote_question(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Upvote question as the current user.
    """
    return questions_service.upvote_question(ctx, uuid=uuid)


@router.delete("/{uuid}/upvotes/", response_model=schemas.QuestionUpvotes)
def cancel_upvote_question(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Cancel upvote for question as the current user.
    """
    return questions_service.cancel_upvote_question(ctx, uuid=uuid)


@router.get("/{uuid}/page", response_model=schemas.QuestionPage)
@limiter.limit("60/minute")
def get_question_page(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
) -> Any:
    return questions_service.get_question_page(ctx, uuid=uuid, request=request)
