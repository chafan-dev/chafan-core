import datetime
from typing import Any

import sentry_sdk
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.encoders import jsonable_encoder

from chafan_core.app import crud, models, schemas
from chafan_core.app.api import deps
from chafan_core.app.api.api_v1.endpoints.submissions import _update_submission
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.common import OperationType
from chafan_core.app.user_permission import check_user_in_site
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.schemas.submission import SubmissionUpdate
from chafan_core.app.schemas.submission_archive import SubmissionEditableSnapshot
from chafan_core.app.schemas.submission_suggestion import (
    SubmissionSuggestionCreate,
    SubmissionSuggestionUpdate,
)
from chafan_core.utils.base import HTTPException_, unwrap

router = APIRouter()


@router.post("/", response_model=schemas.SubmissionSuggestion)
def post_submission_suggestions(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    create_in: SubmissionSuggestionCreate,
    background_tasks: BackgroundTasks,
) -> Any:
    current_user = ctx.get_current_active_user()
    submission = crud.submission.get_by_uuid(
        ctx.get_db(), uuid=create_in.submission_uuid
    )
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exist in the system.",
        )
    check_user_in_site(
        ctx.get_db(),
        site=submission.site,
        user_id=current_user.id,
        op_type=OperationType.WriteSiteSubmission,
    )
    if current_user.remaining_coins < submission.site.create_suggestion_coin_deduction:
        raise HTTPException_(
            status_code=400,
            detail="Insufficient coins.",
        )
    s = crud.submission_suggestion.create_with_author(
        ctx.get_db(),
        obj_in=create_in,
        author_id=current_user.id,
        submission=submission,
    )
    from chafan_core.app.services.postprocess import postprocess_new_submission_suggestion

    background_tasks.add_task(postprocess_new_submission_suggestion, s.id)
    from chafan_core.app.responders import suggestions as suggestions_responder

    return unwrap(
        suggestions_responder.submission_suggestion_schema_from_orm(
            ctx.principal_view, s
        )
    )


def _check_author(
    submission_suggestion: models.SubmissionSuggestion, user_id: int
) -> None:
    if submission_suggestion.submission.author_id != user_id:
        raise HTTPException_(
            status_code=400,
            detail="Only author of submission can do this.",
        )


def _check_suggestion_author(
    submission_suggestion: models.SubmissionSuggestion, user_id: int
) -> None:
    if submission_suggestion.author_id != user_id:
        raise HTTPException_(
            status_code=400,
            detail="Only author of suggestion can do this.",
        )


def _accept_submission_suggestion(
    ctx: RequestContext,
    submission_suggestion: models.SubmissionSuggestion,
    background_tasks: BackgroundTasks,
) -> None:
    # Update the submission
    desc = None
    if submission_suggestion.description:
        desc = RichText(
            source=submission_suggestion.description,
            rendered_text=submission_suggestion.description_text,
            editor=submission_suggestion.description_editor,
        )
    _update_submission(
        ctx,
        submission=submission_suggestion.submission,
        submission_in=SubmissionUpdate(
            title=submission_suggestion.title,
            desc=desc,
            topic_uuids=submission_suggestion.topic_uuids,
        ),
        background_tasks=background_tasks,
    )
    # Rebate the suggestion author
    from chafan_core.app.services.postprocess import postprocess_accept_submission_suggestion

    background_tasks.add_task(
        postprocess_accept_submission_suggestion, submission_suggestion.id
    )


@router.put("/{uuid}", response_model=schemas.SubmissionSuggestion)
def update_submission_suggestions(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
    update_in: SubmissionSuggestionUpdate,
    background_tasks: BackgroundTasks,
) -> Any:
    db = ctx.get_db()
    current_user_id = ctx.unwrapped_principal_id()
    submission_suggestion = crud.submission_suggestion.get_by_uuid(db, uuid=uuid)
    if submission_suggestion is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission_suggestion doesn't exist in the system.",
        )
    check_user_in_site(
        db,
        site=submission_suggestion.submission.site,
        user_id=current_user_id,
        op_type=OperationType.WriteSiteSubmission,
    )
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    old_status = submission_suggestion.status
    new_status = update_in.status
    update_dict = update_in.dict()
    if old_status in ["pending", "rejected"]:
        if new_status == "accepted":
            _check_author(submission_suggestion, current_user_id)
            update_dict["accepted_at"] = utc_now
            original_desc = None
            if submission_suggestion.submission.description:
                original_desc = RichText(
                    source=submission_suggestion.submission.description,
                    editor=submission_suggestion.submission.description_editor,
                    rendered_text=submission_suggestion.submission.description_text,
                )
            submission_suggestion.accepted_diff_base = jsonable_encoder(
                SubmissionEditableSnapshot(
                    title=submission_suggestion.submission.title,
                    desc=original_desc,
                    topic_uuids=[
                        t.name for t in submission_suggestion.submission.topics
                    ],
                )
            )
            if (
                submission_suggestion.author
                not in submission_suggestion.submission.contributors
            ):
                submission_suggestion.submission.contributors.append(
                    submission_suggestion.author
                )
            db.commit()
            _accept_submission_suggestion(ctx, submission_suggestion, background_tasks=background_tasks)
        elif new_status == "rejected":
            _check_author(submission_suggestion, current_user_id)
            update_dict["rejected_at"] = utc_now
        elif new_status == "retracted":
            _check_suggestion_author(submission_suggestion, current_user_id)
            update_dict["retracted_at"] = utc_now
        else:
            sentry_sdk.capture_message(f"Unknown submission status: {old_status}")
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
        _check_suggestion_author(submission_suggestion, current_user_id)
        update_dict["retracted_at"] = None
    else:
        raise HTTPException_(
            status_code=400,
            detail=f"Unsupported status.",
        )
    s = crud.submission_suggestion.update(
        db, db_obj=submission_suggestion, obj_in=update_dict
    )
    from chafan_core.app.responders import suggestions as suggestions_responder

    return unwrap(
        suggestions_responder.submission_suggestion_schema_from_orm(
            ctx.principal_view, s
        )
    )
