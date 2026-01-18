from typing import Optional

from pydantic import BaseModel

from chafan_core.utils.validators import (
    CaseInsensitiveEmailStr,
    CountryCode,
    SubscriberNumber,
)


class IntlPhoneNumber(BaseModel):
    country_code: CountryCode
    subscriber_number: SubscriberNumber

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
