from typing import Any

from fastapi import APIRouter, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import forms as forms_service

router = APIRouter()


@router.post("/", response_model=schemas.FormResponse)
def create_form_response(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    form_response_in: schemas.FormResponseCreate,
) -> Any:
    return forms_service.create_form_response(ctx, form_response_in=form_response_in)
