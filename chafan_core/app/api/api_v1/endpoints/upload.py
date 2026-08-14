from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile

from chafan_core.app import object_storage, schemas
from chafan_core.app.api import deps
from chafan_core.app.common import valid_content_length
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.limiter import limiter
from chafan_core.app.services import uploads as uploads_service
from chafan_core.utils.base import HTTPException_

router = APIRouter()


@router.post("/images/", response_model=schemas.UploadedImage)
@limiter.limit("20/hour;60/day")
def upload_image(
    request: Request,
    response: Response,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    file: UploadFile = File(...),
    file_size: int = Depends(valid_content_length),
    purpose: str = Form("figure"),
) -> Any:
    if not object_storage.is_configured():
        raise HTTPException_(
            status_code=503, detail="Image uploads are not configured on this server."
        )
    return uploads_service.upload_image(
        ctx, file=file, file_size=file_size, purpose=purpose
    )
