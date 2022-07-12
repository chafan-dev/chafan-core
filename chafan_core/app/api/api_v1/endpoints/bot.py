from typing import Any

from fastapi import APIRouter, Depends

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.app.api.api_v1.endpoints.submissions import _create_submission
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.config import settings
from chafan_core.app.schemas.security import VerifiedTelegramID, VerifyTelegramID
from chafan_core.utils.base import HTTPException_

router = APIRouter()


@router.post("/verify-telegram-id/", response_model=schemas.VerifyTelegramResponse)
def verify_telegram_id(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    data: VerifyTelegramID,
) -> Any:
    if (
        (not settings.OFFICIAL_BOT_SECRET)
        or data.verifier_secret != settings.OFFICIAL_BOT_SECRET
        or (not cached_layer.is_valid_verification_code(data.email, data.code))
    ):
        raise HTTPException_(
            status_code=400,
            detail="Unauthenticated.",
        )
    user = crud.user.get_by_email(cached_layer.get_db(), email=data.email)
    if user is None:
        raise HTTPException_(
            status_code=400,
            detail="Invalid email.",
        )
    crud.user.update(
        cached_layer.get_db(),
        db_obj=user,
        obj_in={"verified_telegram_user_id": data.telegram_id},
    )
    return schemas.VerifyTelegramResponse(handle=user.handle)


@router.post("/submissions/", response_model=schemas.Submission)
def create_submission(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    submission_in: schemas.SubmissionCreate,
    verified_id: VerifiedTelegramID,
) -> Any:
    if (
        not settings.OFFICIAL_BOT_SECRET
    ) or verified_id.verifier_secret != settings.OFFICIAL_BOT_SECRET:
        raise HTTPException_(
            status_code=400,
            detail="Unauthenticated.",
        )
    user = crud.user.get_by_telegram_id(
        cached_layer.get_db(), telegram_id=verified_id.telegram_id
    )
    if not user:
        raise HTTPException_(
            status_code=400,
            detail="User doesn't exist.",
        )
    return _create_submission(cached_layer, submission_in, user)
