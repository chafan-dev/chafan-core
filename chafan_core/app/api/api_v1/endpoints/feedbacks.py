from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Request, Response, BackgroundTasks
from fastapi.datastructures import UploadFile
from fastapi.param_functions import File, Form
from sqlalchemy.orm import Session

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.common import valid_content_length
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.limiter import limiter
from chafan_core.app.services import feedbacks as feedbacks_service
from chafan_core.utils.validators import CaseInsensitiveEmailStr

router = APIRouter()


@router.get("/", response_model=List[schemas.Feedback])
def get_my_feedbacks(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    return feedbacks_service.list_my_feedbacks(ctx)


@router.get("/{feedback_id}/screenshot", response_class=Response)
def get_feedback_screenshot(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    feedback_id: int,
) -> Any:
    blob = feedbacks_service.get_feedback_screenshot_bytes(ctx, feedback_id=feedback_id)
    return Response(content=blob, media_type="image/jpeg")


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
    background_tasks: BackgroundTasks,
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
    feedback = feedbacks_service.create_feedback(
        db,
        description=description,
        location_url=location_url,
        email=email,
        screenshot_blob=screenshot_blob,
        current_user_id=current_user_id,
    )
    from chafan_core.app.services.postprocess import postprocess_new_feedback

    background_tasks.add_task(postprocess_new_feedback, feedback.id)
    return schemas.GenericResponse()
