"""User feedback domain service."""

from __future__ import annotations

import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from chafan_core.app import crud, schemas
from chafan_core.app.models.feedback import Feedback
from chafan_core.app.responders import misc as misc_responder
from chafan_core.utils.base import HTTPException_
from chafan_core.utils.validators import CaseInsensitiveEmailStr


def list_my_feedbacks(ctx) -> List[schemas.Feedback]:
    current_user = ctx.get_current_active_user()
    mat = ctx.principal_view
    return [
        misc_responder.feedback_schema_from_orm(mat, f)
        for f in current_user.feedbacks
    ]


def get_feedback_screenshot_bytes(ctx, *, feedback_id: int) -> bytes:
    current_user = ctx.get_current_active_user()
    feedback = crud.feedback.get(ctx.get_db(), id=feedback_id)
    if not feedback:
        raise HTTPException_(
            status_code=400,
            detail="The feedback doesn't exist.",
        )
    if not (
        (feedback.user and feedback.user.id == current_user.id)
        or current_user.is_superuser
    ):
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    if not feedback.screenshot_blob:
        raise HTTPException_(
            status_code=400,
            detail="The feedback has no screenshot.",
        )
    return feedback.screenshot_blob


def create_feedback(
    db: Session,
    *,
    description: str,
    location_url: Optional[str],
    email: Optional[CaseInsensitiveEmailStr],
    screenshot_blob: Optional[bytes],
    current_user_id: Optional[int],
) -> Feedback:
    feedback = Feedback(
        created_at=datetime.datetime.now(tz=datetime.timezone.utc),
        user_id=current_user_id,
        user_email=email,
        description=description,
        screenshot_blob=screenshot_blob,
        location_url=location_url,
    )
    db.add(feedback)
    db.commit()
    return feedback
