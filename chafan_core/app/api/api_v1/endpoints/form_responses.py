from typing import Any, List

from fastapi import APIRouter, Depends
from pydantic.tools import parse_obj_as

from chafan_core.app import crud, models, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.schemas.form import (
    FormField,
    MultipleChoicesField,
    SingleChoiceField,
    TextField,
)
from chafan_core.app.schemas.form_response import (
    FormResponseField,
    MultipleChoiceResponseField,
    SingleChoiceResponseField,
    TextResponseField,
)
from chafan_core.utils.base import HTTPException_

router = APIRouter()


def validate_form_response(
    form: models.Form, response_fields: List[FormResponseField]
) -> None:
    indexed_response_fields = {f.unique_name: f for f in response_fields}
    for form_field in parse_obj_as(List[FormField], form.form_fields):
        assert form_field.unique_name in indexed_response_fields
        response_field = indexed_response_fields[form_field.unique_name]
        if isinstance(form_field.field_type, TextField):
            assert isinstance(response_field.field_content, TextResponseField)
        elif isinstance(form_field.field_type, MultipleChoicesField):
            assert isinstance(response_field.field_content, MultipleChoiceResponseField)
            assert all(
                selected in form_field.field_type.choices
                for selected in response_field.field_content.selected_choices
            )
        elif isinstance(form_field.field_type, SingleChoiceField):
            assert isinstance(response_field.field_content, SingleChoiceResponseField)
            assert (
                response_field.field_content.selected_choice
                in form_field.field_type.choices
            )
        else:
            raise Exception(f"Unknown field: {form_field.field_type}")


@router.post("/", response_model=schemas.FormResponse)
def create_form_response(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    form_response_in: schemas.FormResponseCreate,
) -> Any:
    db = cached_layer.get_db()
    form = crud.form.get_by_uuid(db, uuid=form_response_in.form_uuid)
    if form is None:
        raise HTTPException_(
            status_code=400,
            detail="The form doesn't exists in the system.",
        )
    validate_form_response(form, form_response_in.response_fields)
    return cached_layer.materializer.form_response_schema_from_orm(
        crud.form_response.create_with_author(
            db,
            obj_in=form_response_in,
            response_author_id=cached_layer.unwrapped_principal_id(),
            form=form,
        )
    )
