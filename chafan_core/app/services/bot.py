"""Official bot domain service."""

from __future__ import annotations

from chafan_core.app import crud, schemas, security
from chafan_core.app.config import settings
from chafan_core.app.schemas.security import VerifiedTelegramID, VerifyTelegramID
from chafan_core.app.services import submissions as submissions_service
from chafan_core.utils.base import HTTPException_


def verify_telegram_id(ctx, data: VerifyTelegramID) -> schemas.VerifyTelegramResponse:
    if (
        (not settings.OFFICIAL_BOT_SECRET)
        or data.verifier_secret != settings.OFFICIAL_BOT_SECRET
        or (not security.check_digit_verification_code(data.email, data.code))
    ):
        raise HTTPException_(
            status_code=400,
            detail="Unauthenticated.",
        )
    user = crud.user.get_by_email(ctx.get_db(), email=data.email)
    if user is None:
        raise HTTPException_(
            status_code=400,
            detail="Invalid email.",
        )
    crud.user.update(
        ctx.get_db(),
        db_obj=user,
        obj_in={"verified_telegram_user_id": data.telegram_id},
    )
    return schemas.VerifyTelegramResponse(handle=user.handle)


def create_submission_as_bot(
    ctx, *, submission_in: schemas.SubmissionCreate, verified_id: VerifiedTelegramID
) -> schemas.Submission:
    if (
        not settings.OFFICIAL_BOT_SECRET
    ) or verified_id.verifier_secret != settings.OFFICIAL_BOT_SECRET:
        raise HTTPException_(
            status_code=400,
            detail="Unauthenticated.",
        )
    user = crud.user.get_by_telegram_id(
        ctx.get_db(), telegram_id=verified_id.telegram_id
    )
    if not user:
        raise HTTPException_(
            status_code=400,
            detail="User doesn't exist.",
        )
    _sub, data = submissions_service.create_submission(
        ctx, submission_in=submission_in, author=user
    )
    return data
