from typing import Any, Optional

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import comments as comments_service
from chafan_core.app.task import postprocess_comment_update, postprocess_new_comment
from chafan_core.utils.base import HTTPException_

router = APIRouter()


@router.get("/{uuid}", response_model=schemas.Comment)
def get_comment(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
) -> Any:
    """Get a comment in one of the current user's belonging sites."""
    data = comments_service.get_comment_schema(ctx, uuid)
    if data is None:
        raise HTTPException_(
            status_code=400,
            detail="The comment doesn't exist in the system.",
        )
    return data


@router.get("/{uuid}/upvotes/", response_model=schemas.CommentUpvotes)
def get_comment_upvotes(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    data = comments_service.get_comment_upvotes(
        db, uuid=uuid, principal_id=current_user_id
    )
    if data is None:
        raise HTTPException_(
            status_code=400,
            detail="The comment doesn't exist in the system.",
        )
    return data


@router.delete("/{uuid}", response_model=schemas.GenericResponse)
def delete_comment(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    err = comments_service.delete_comment(
        db, uuid=uuid, principal_id=current_user_id
    )
    if err is not None:
        raise HTTPException_(status_code=400, detail=err)
    return schemas.GenericResponse()


@router.post("/", response_model=schemas.Comment)
def create_comment(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    comment_in: schemas.CommentCreate,
    background_tasks: BackgroundTasks,
) -> Any:
    """Create new comment authored by the current active user."""
    comment, comment_data = comments_service.create_comment(ctx, comment_in=comment_in)
    background_tasks.add_task(
        postprocess_new_comment,
        comment.id,
        comment_in.shared_to_timeline,
        comment_in.mentioned,
    )
    return comment_data


@router.put("/{uuid}", response_model=schemas.Comment)
def update_comment(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
    comment_in: schemas.CommentUpdate,
    background_tasks: BackgroundTasks,
) -> Any:
    """Update comment authored by the current user."""
    comment, comment_data, was_shared = comments_service.update_comment(
        ctx, uuid=uuid, comment_in=comment_in
    )
    background_tasks.add_task(
        postprocess_comment_update,
        comment.id,
        was_shared,
        shared_to_timeline=comment_in.shared_to_timeline,
        mentioned=comment_in.mentioned,
    )
    return comment_data


@router.post("/{uuid}/upvotes/", response_model=schemas.CommentUpvotes)
def upvote_comment(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """Upvote comment as the current user."""
    return comments_service.upvote_comment(ctx, uuid=uuid)


@router.delete("/{uuid}/upvotes/", response_model=schemas.CommentUpvotes)
def cancel_upvote_comment(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """Cancel upvote for comment as the current user."""
    return comments_service.cancel_upvote_comment(ctx, uuid=uuid)
