import datetime
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, field_validator

from chafan_core.app.schemas.preview import UserPreview


# Shared properties
class FormBase(BaseModel):
    pass


class TextField(BaseModel):
    field_type_name: Literal["text_field"] = "text_field"
    desc: str


class SingleChoiceField(BaseModel):
    field_type_name: Literal["single_choice_field"] = "single_choice_field"
    desc: str
    # TODO: validate
    choices: List[str]
    correct_choice: Optional[str] = None
    score: Optional[int] = None


class MultipleChoicesField(BaseModel):
    field_type_name: Literal["multiple_choices_field"] = "multiple_choices_field"
    desc: str
    # TODO: validate
    choices: List[str]
    correct_choices: Optional[List[str]] = None
    score_per_correct_choice: Optional[int] = None


class SingleChoiceFieldPublic(BaseModel):
    field_type_name: Literal["single_choice_field"] = "single_choice_field"
    desc: str
    # TODO: validate
    choices: List[str]


class MultipleChoicesFieldPublic(BaseModel):
    field_type_name: Literal["multiple_choices_field"] = "multiple_choices_field"
    desc: str
    # TODO: validate
    choices: List[str]


class FormField(BaseModel):
    unique_name: str
    field_type: Union[TextField, SingleChoiceField, MultipleChoicesField]


class FormFieldPublic(BaseModel):
    unique_name: str
    field_type: Union[TextField, SingleChoiceFieldPublic, MultipleChoicesFieldPublic]


# Properties to receive via API on creation
class FormCreate(FormBase):
    title: str
    form_fields: List[FormField]

    @field_validator("form_fields")
    @classmethod
    def _valid_form_fields(cls, v: List[FormField]) -> List[FormField]:
        if len(set(f.unique_name for f in v)) != len(v):
            raise ValueError("Form field names must be unique")
        return v


class FormUpdate(FormBase):
    pass


class FormInDBBase(FormBase):
    title: str
    uuid: str
    form_fields: List[FormField]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class Form(FormInDBBase):
    author: UserPreview


class FormPublic(BaseModel):
    title: str
    uuid: str
    form_fields: List[FormFieldPublic]
    author: UserPreview
