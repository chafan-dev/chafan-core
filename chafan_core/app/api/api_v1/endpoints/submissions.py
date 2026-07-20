from typing import Any, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.common import client_ip
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import submissions as submissions_service
from chafan_core.app.services.postprocess import (
    postprocess_new_submission,
    postprocess_updated_submission,
)

router = APIRouter()


# TODO: paging
@router.get(
    "/",
    response_model=List[schemas.Submission],
)
def get_submissions_for_user(
    ctx: RequestContext = Depends(deps.get_request_context),
) -> Any:
    return submissions_service.submissions_for_user(ctx, ctx.principal_id)


@router.get(
    "/{uuid}", response_model=schemas.Submission
)
def get_submission(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
) -> Any:
    """
    Get submission in one of current_user's belonging sites.
    """
    return submissions_service.get_submission(ctx, uuid=uuid)


@router.get("/{uuid}/upvotes/", response_model=schemas.SubmissionUpvotes)
def get_submission_upvotes(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    return submissions_service.get_upvotes(
        db, uuid=uuid, principal_id=current_user_id
    )


@router.post("/{uuid}/views/", response_model=schemas.GenericResponse)
def bump_views_counter(
    *,
    uuid: str,
    ctx: RequestContext = Depends(deps.get_request_context),
) -> Any:
    submissions_service.bump_views(ctx, uuid=uuid)
    return schemas.GenericResponse()


@router.post("/", response_model=schemas.Submission)
def create_submission(
    request: Request,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    submission_in: schemas.SubmissionCreate,
    background_tasks: BackgroundTasks,
) -> Any:
    """
    Create new submission authored by the current user in one of the belonging sites.
    """
    current_user = ctx.get_current_active_user()
    new_submission, data = submissions_service.create_submission(
        ctx,
        submission_in=submission_in,
        author=current_user,
        ipaddr=client_ip(request),
    )
    background_tasks.add_task(postprocess_new_submission, new_submission.id)
    return data


@router.put("/{uuid}", response_model=schemas.Submission)
def update_submission(
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
    submission_in: schemas.SubmissionUpdate,
    background_tasks: BackgroundTasks,
) -> Any:
    """
    Update submission as author.
    """
    new_submission, data = submissions_service.update_submission(
        ctx,
        uuid=uuid,
        submission_in=submission_in,
        ipaddr=client_ip(request),
    )
    background_tasks.add_task(postprocess_updated_submission, new_submission.id)
    return data


@router.get("/{uuid}/archives/", response_model=List[schemas.SubmissionArchive])
def get_submission_archives(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    """
    Get answer's archives as its author.
    """
    return submissions_service.list_archives(
        db, uuid=uuid, principal_id=current_user_id
    )


@router.get("/{uuid}/suggestions/", response_model=List[schemas.SubmissionSuggestion])
def get_submission_suggestions(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
) -> Any:
    return submissions_service.list_suggestions(ctx, uuid=uuid)


@router.put("/{uuid}/hide", response_model=Optional[schemas.Submission])
def hide_submission(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    return submissions_service.hide_submission(ctx, uuid=uuid)


@router.post("/{uuid}/upvotes/", response_model=schemas.SubmissionUpvotes)
def upvote_submission(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Upvote submission as the current user.
    """
    return submissions_service.upvote_submission(ctx, uuid=uuid)


@router.delete("/{uuid}/upvotes/", response_model=schemas.SubmissionUpvotes)
def cancel_upvote_submission(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Cancel upvote for submission as the current user.
    """
    return submissions_service.cancel_upvote_submission(ctx, uuid=uuid)
