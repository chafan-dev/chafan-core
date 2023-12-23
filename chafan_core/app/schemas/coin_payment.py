import datetime
from typing import Optional

from pydantic import BaseModel

from chafan_core.app.schemas.event import Event
from chafan_core.app.schemas.preview import UserPreview


# Shared properties
class CoinPaymentBase(BaseModel):
    pass


# Properties to receive via API on creation
class CoinPaymentCreate(CoinPaymentBase):
    payee_id: int
    amount: int
    event_json: str
    comment: Optional[str] = None


# Properties to receive via API on update
class CoinPaymentUpdate(CoinPaymentBase):
    pass


class CoinPaymentInDBBase(CoinPaymentBase):
    id: int
    created_at: datetime.datetime
    amount: int
    comment: Optional[str]

    class Config:
        from_attributes = True


# Additional properties to return via API
class CoinPayment(CoinPaymentInDBBase):
    payer: UserPreview
    payee: UserPreview
    event: Optional[Event]
