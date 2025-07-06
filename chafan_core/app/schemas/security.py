from typing import Optional

from pydantic import BaseModel, validator

from chafan_core.utils.validators import CaseInsensitiveEmailStr


class IntlPhoneNumber(BaseModel):
    country_code: str
    subscriber_number: str

    @validator("country_code")
    def _valid_country_code(cls, v: str) -> str:
        if v.isdigit() and len(v) >= 1 and len(v) <= 3:
            return v
        raise ValueError(f"Invalid country code: {v}")

    @validator("subscriber_number")
    def _valid_subscriber_number(cls, v: str) -> str:
        if v.isdigit() and len(v) >= 1 and len(v) <= 12:
            return v
        raise ValueError(f"Invalid subscriber number: {v}")

    def format_e164(self) -> str:
        return f"+{self.country_code}{self.subscriber_number}"


class VerificationCodeRequest(BaseModel):
    email: Optional[CaseInsensitiveEmailStr]


class LoginWithVerificationCode(BaseModel):
    phone_number: IntlPhoneNumber
    code: str


class VerifyTelegramID(BaseModel):
    verifier_secret: str
    telegram_id: str
    email: str
    code: str


class VerifiedTelegramID(BaseModel):
    verifier_secret: str
    telegram_id: str
