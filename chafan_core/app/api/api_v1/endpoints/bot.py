from typing import Any

from fastapi import APIRouter, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.schemas.security import VerifiedTelegramID, VerifyTelegramID
from chafan_core.app.services import bot as bot_service

router = APIRouter()


@router.post("/verify-telegram-id/", response_model=schemas.VerifyTelegramResponse)
def verify_telegram_id(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    data: VerifyTelegramID,
) -> Any:
    return bot_service.verify_telegram_id(ctx, data)


@router.post("/submissions/", response_model=schemas.Submission)
def create_submission(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    submission_in: schemas.SubmissionCreate,
    verified_id: VerifiedTelegramID,
) -> Any:
    return bot_service.create_submission_as_bot(
        ctx, submission_in=submission_in, verified_id=verified_id
    )
