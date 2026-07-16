from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.schemas.submission_suggestion import (
    SubmissionSuggestionCreate,
    SubmissionSuggestionUpdate,
)
from chafan_core.app.services import submission_suggestions as submission_suggestions_service
from chafan_core.app.services.postprocess import (
    postprocess_accept_submission_suggestion,
    postprocess_new_submission_suggestion,
    postprocess_updated_submission,
)

router = APIRouter()


@router.post("/", response_model=schemas.SubmissionSuggestion)
def post_submission_suggestions(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    create_in: SubmissionSuggestionCreate,
    background_tasks: BackgroundTasks,
) -> Any:
    s, data = submission_suggestions_service.create_suggestion(
        ctx, create_in=create_in
    )
    background_tasks.add_task(postprocess_new_submission_suggestion, s.id)
    return data


@router.put("/{uuid}", response_model=schemas.SubmissionSuggestion)
def update_submission_suggestions(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
    update_in: SubmissionSuggestionUpdate,
    background_tasks: BackgroundTasks,
) -> Any:
    (
        data,
        needs_accept_postprocess,
        suggestion,
        updated_submission,
    ) = submission_suggestions_service.update_suggestion(
        ctx, uuid=uuid, update_in=update_in
    )
    if updated_submission is not None:
        background_tasks.add_task(
            postprocess_updated_submission, updated_submission.id
        )
    if needs_accept_postprocess and suggestion is not None:
        background_tasks.add_task(
            postprocess_accept_submission_suggestion, suggestion.id
        )
    return data
