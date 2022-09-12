import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Request, Response
from fastapi.datastructures import UploadFile
from fastapi.param_functions import File, Form
from sqlalchemy.orm import Session

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import run_dramatiq_task, valid_content_length
from chafan_core.app.limiter import limiter
from chafan_core.app.models.feedback import Feedback
from chafan_core.app.task import postprocess_new_feedback
from chafan_core.utils.base import HTTPException_
from chafan_core.utils.validators import CaseInsensitiveEmailStr

router = APIRouter()


@router.get("/", response_model=List[schemas.Feedback])
def get_my_feedbacks(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
) -> Any:
    current_user = cached_layer.get_current_active_user()
    return [
        cached_layer.materializer.feedback_schema_from_orm(f)
        for f in current_user.feedbacks
    ]


@router.get("/{feedback_id}/screenshot", response_class=Response)
def get_feedback_screenshot(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    feedback_id: int,
) -> Any:
    current_user = cached_layer.get_current_active_user()
    feedback = crud.feedback.get(cached_layer.get_db(), id=feedback_id)
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
    return Response(content=feedback.screenshot_blob, media_type="image/jpeg")


@router.post("/", response_model=schemas.GenericResponse)
@limiter.limit("10/day")
def post_feedback(
    response: Response,
    request: Request,
    *,
    db: Session = Depends(deps.get_db),
    file: Optional[UploadFile] = File(None),
    description: str = Form(...),
    location_url: Optional[str] = Form(None),
    email: Optional[CaseInsensitiveEmailStr] = Form(None),
    file_size: int = Depends(valid_content_length),
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    screenshot_blob = None
    if file:
        screenshot_blob = b""
        written_size = 0
        while written_size < file_size:
            chunk = file.file.read(file_size - written_size)
            if len(chunk) == 0:
                break
            written_size += len(chunk)
            screenshot_blob += chunk
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
    run_dramatiq_task(postprocess_new_feedback, feedback.id)
    return schemas.GenericResponse()
