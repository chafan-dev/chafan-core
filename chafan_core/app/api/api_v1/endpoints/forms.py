from typing import Any, List

from fastapi import APIRouter, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import forms as forms_service

router = APIRouter()


@router.get("/{uuid}", response_model=schemas.Form)
def get_form(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
) -> Any:
    return forms_service.get_form(ctx, uuid)


@router.get("/", response_model=List[schemas.Form], include_in_schema=False)
def get_forms(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    return forms_service.list_my_forms(ctx)


@router.post("/", response_model=schemas.Form, include_in_schema=False)
def create_form(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    form_in: schemas.FormCreate,
) -> Any:
    return forms_service.create_form(ctx, form_in=form_in)


@router.get(
    "/{uuid}/responses/",
    response_model=List[schemas.FormResponse],
    include_in_schema=False,
)
def get_form_responses(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
) -> Any:
    return forms_service.list_form_responses(ctx, uuid=uuid)
