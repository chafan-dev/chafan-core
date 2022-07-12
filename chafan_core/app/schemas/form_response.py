import datetime
from typing import List, Literal, Union

from pydantic import BaseModel, validator

from chafan_core.app.schemas.form import Form
from chafan_core.app.schemas.preview import UserPreview


# Shared properties
class FormResponseBase(BaseModel):
    pass


class TextResponseField(BaseModel):
    field_type_name: Literal["text_response_field"] = "text_response_field"
    desc: str
    text: str


class SingleChoiceResponseField(BaseModel):
    field_type_name: Literal[
        "single_choice_response_field"
    ] = "single_choice_response_field"
    desc: str
    # TODO: validate
    selected_choice: str


class MultipleChoiceResponseField(BaseModel):
    field_type_name: Literal[
        "multiple_choices_response_field"
    ] = "multiple_choices_response_field"
    desc: str
    # TODO: validate
    selected_choices: List[str]


class FormResponseField(BaseModel):
    unique_name: str
    field_content: Union[
        TextResponseField, SingleChoiceResponseField, MultipleChoiceResponseField
    ]


# Properties to receive via API on creation
class FormResponseCreate(FormResponseBase):
    form_uuid: str
    response_fields: List[FormResponseField]

    @validator("response_fields")
    def _valid_response_fields(
        cls, v: List[FormResponseField]
    ) -> List[FormResponseField]:
        assert len(set(f.unique_name for f in v)) == len(v)
        return v


# Properties to receive via API on update
class FormResponseUpdate(FormResponseBase):
    pass


class FormResponseInDBBase(FormResponseBase):
    id: int
    response_fields: List[FormResponseField]
    created_at: datetime.datetime

    class Config:
        orm_mode = True


# Additional properties to return via API
class FormResponse(FormResponseInDBBase):
    response_author: UserPreview
    form: Form
