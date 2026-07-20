from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.schemas.answer_suggest_edit import (
    AnswerSuggestEditCreate,
    AnswerSuggestEditUpdate,
)
from chafan_core.app.services import answer_suggest_edits as answer_suggest_edits_service
from chafan_core.app.services.postprocess import (
    postprocess_accept_answer_suggest_edit,
    postprocess_new_answer,
    postprocess_new_answer_suggest_edit,
)

router = APIRouter()


@router.post("/", response_model=schemas.AnswerSuggestEdit)
def post_answer_suggest_edits(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    create_in: AnswerSuggestEditCreate,
    background_tasks: BackgroundTasks,
) -> Any:
    s, data = answer_suggest_edits_service.create_suggest_edit(
        ctx, create_in=create_in
    )
    background_tasks.add_task(postprocess_new_answer_suggest_edit, s.id)
    return data


@router.put("/{uuid}", response_model=schemas.AnswerSuggestEdit)
def update_answer_suggest_edits(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
    update_in: AnswerSuggestEditUpdate,
    background_tasks: BackgroundTasks,
) -> Any:
    (
        data,
        needs_accept_postprocess,
        suggest_edit,
        accepted_answer,
        answer_needs_postprocess,
        answer_was_published,
    ) = answer_suggest_edits_service.update_suggest_edit(
        ctx, uuid=uuid, update_in=update_in
    )
    if answer_needs_postprocess and accepted_answer is not None:
        background_tasks.add_task(
            postprocess_new_answer, accepted_answer.id, answer_was_published
        )
    if needs_accept_postprocess and suggest_edit is not None:
        background_tasks.add_task(
            postprocess_accept_answer_suggest_edit, suggest_edit.id
        )
    return data
