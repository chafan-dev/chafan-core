"""Forms and form-response domain service."""

from __future__ import annotations

from typing import List

from pydantic.tools import parse_obj_as

from chafan_core.app import crud, models, schemas
from chafan_core.app.responders import misc as misc_responder
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


def form_schema(ctx, form: models.Form) -> schemas.Form:
    return misc_responder.form_schema_from_orm(ctx.materializer, form)


def form_response_schema(ctx, form_response: models.FormResponse) -> schemas.FormResponse:
    return misc_responder.form_response_schema_from_orm(
        ctx.materializer, form_response
    )


def get_form(ctx, uuid: str) -> schemas.Form:
    form = crud.form.get_by_uuid(ctx.get_db(), uuid=uuid)
    if form is None:
        raise HTTPException_(
            status_code=400,
            detail="The form doesn't exist in the system.",
        )
    return form_schema(ctx, form)


def list_my_forms(ctx) -> List[schemas.Form]:
    current_user = ctx.get_current_active_user()
    return [form_schema(ctx, form) for form in current_user.forms]


def create_form(ctx, *, form_in: schemas.FormCreate) -> schemas.Form:
    current_user = ctx.get_current_active_user()
    form = crud.form.create_with_author(
        ctx.get_db(),
        obj_in=form_in,
        author=current_user,
    )
    return form_schema(ctx, form)


def list_form_responses(ctx, *, uuid: str) -> List[schemas.FormResponse]:
    form = crud.form.get_by_uuid(ctx.get_db(), uuid=uuid)
    if form is None:
        raise HTTPException_(
            status_code=400,
            detail="The form doesn't exist in the system.",
        )
    if form.author_id != ctx.unwrapped_principal_id():
        raise HTTPException_(
            status_code=400,
            detail="The form doesn't belong to current user.",
        )
    return [form_response_schema(ctx, r) for r in form.responses]


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


def create_form_response(
    ctx, *, form_response_in: schemas.FormResponseCreate
) -> schemas.FormResponse:
    db = ctx.get_db()
    form = crud.form.get_by_uuid(db, uuid=form_response_in.form_uuid)
    if form is None:
        raise HTTPException_(
            status_code=400,
            detail="The form doesn't exist in the system.",
        )
    validate_form_response(form, form_response_in.response_fields)
    created = crud.form_response.create_with_author(
        db,
        obj_in=form_response_in,
        response_author_id=ctx.unwrapped_principal_id(),
        form=form,
    )
    return form_response_schema(ctx, created)
