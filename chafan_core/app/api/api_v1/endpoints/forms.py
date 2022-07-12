from typing import Any, List

from fastapi import APIRouter, Depends

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.utils.base import HTTPException_

router = APIRouter()


@router.get("/{uuid}", response_model=schemas.Form)
def get_form(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
) -> Any:
    form = crud.form.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if form is None:
        raise HTTPException_(
            status_code=400,
            detail="The form doesn't exists in the system.",
        )
    return cached_layer.materializer.form_schema_from_orm(form)


@router.get("/", response_model=List[schemas.Form], include_in_schema=False)
def get_forms(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
) -> Any:
    current_user = cached_layer.get_current_active_user()
    return [
        cached_layer.materializer.form_schema_from_orm(form)
        for form in current_user.forms
    ]


@router.post("/", response_model=schemas.Form, include_in_schema=False)
def create_form(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    form_in: schemas.FormCreate,
) -> Any:
    current_user = cached_layer.get_current_active_user()
    return cached_layer.materializer.form_schema_from_orm(
        crud.form.create_with_author(
            cached_layer.get_db(),
            obj_in=form_in,
            author=current_user,
        )
    )


@router.get(
    "/{uuid}/responses/",
    response_model=List[schemas.FormResponse],
    include_in_schema=False,
)
def get_form_responses(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
) -> Any:
    form = crud.form.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if form is None:
        raise HTTPException_(
            status_code=400,
            detail="The form doesn't exists in the system.",
        )
    if form.author_id != cached_layer.unwrapped_principal_id():
        raise HTTPException_(
            status_code=400,
            detail="The form doesn't belong to current user.",
        )
    return [
        cached_layer.materializer.form_response_schema_from_orm(r)
        for r in form.responses
    ]
