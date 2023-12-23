import datetime
from typing import Optional

from pydantic import BaseModel


# Shared properties
class CoinDepositBase(BaseModel):
    pass


class CoinDepositReference(BaseModel):
    action: str
    object_id: str


# Properties to receive via API on creation
class CoinDepositCreate(CoinDepositBase):
    payee_id: int
    amount: int
    ref_id: str
    comment: Optional[str]


# Properties to receive via API on update
class CoinDepositUpdate(CoinDepositBase):
    pass


class CoinDepositInDBBase(CoinDepositBase):
    id: int
    created_at: datetime.datetime
    amount: int
    ref_id: str
    authorizer_id: int
    payee_id: int
    comment: Optional[str]

    class Config:
        from_attributes = True


# Additional properties to return via API
class CoinDeposit(CoinDepositInDBBase):
    pass


# Additional properties stored in DB
class CoinDepositInDB(CoinDepositInDBBase):
    pass
