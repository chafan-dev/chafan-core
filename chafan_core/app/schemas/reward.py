import datetime
from typing import Literal, Optional

from pydantic import BaseModel, validator

from chafan_core.app.schemas.preview import UserPreview


class AnsweredQuestionCondition(BaseModel):
    condition_type: Literal["answered_question"] = "answered_question"
    question_uuid: str


# Shared properties
class RewardBase(BaseModel):
    pass


class RewardCondition(BaseModel):
    content: AnsweredQuestionCondition


# Properties to receive via API on creation
class RewardCreate(RewardBase):
    expired_after_days: int
    receiver_uuid: str
    coin_amount: int
    note_to_receiver: Optional[str] = None
    condition: Optional[RewardCondition] = None

    @validator("coin_amount")
    def _valid_coin_amount(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Invalid coin amount.")
        return v

    @validator("expired_after_days")
    def _valid_expired_after_days(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Invalid expiry days.")
        return v


class RewardUpdate(BaseModel):
    pass


class RewardInDBBase(RewardBase):
    id: int
    created_at: datetime.datetime
    expired_at: datetime.datetime
    claimed_at: Optional[datetime.datetime]
    refunded_at: Optional[datetime.datetime]
    coin_amount: int
    note_to_receiver: Optional[str]

    class Config:
        orm_mode = True


# Additional properties to return via API
class Reward(RewardInDBBase):
    giver: UserPreview
    receiver: UserPreview
    condition: Optional[RewardCondition] = None
