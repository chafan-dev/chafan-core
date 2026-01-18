import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field

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
    expired_after_days: Annotated[int, Field(gt=0, description="Expiry days")]
    receiver_uuid: str
    coin_amount: Annotated[int, Field(gt=0, description="Coin amount")]
    note_to_receiver: Optional[str] = None
    condition: Optional[RewardCondition] = None


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
        from_attributes = True


# Additional properties to return via API
class Reward(RewardInDBBase):
    giver: UserPreview
    receiver: UserPreview
    condition: Optional[RewardCondition] = None
