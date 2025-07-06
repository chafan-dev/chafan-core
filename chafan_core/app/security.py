import datetime
from typing import Any, Optional, Union

import random

from jose import jwt
from passlib.context import CryptContext  # type: ignore
from pydantic.types import SecretStr

from chafan_core.utils.validators import CaseInsensitiveEmailStr
from chafan_core.app.config import settings
from chafan_core.utils.base import unwrap

from chafan_core.app.common import (
    check_email,
    client_ip,
    get_redis_cli,
    is_dev,
)

import logging
logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


ALGORITHM = "HS256"


async def check_digit_verification_code(email:str, code:str) -> bool:
    #logger.info("Check verification code")
    bypass = settings.DEBUG_BYPASS_REDIS_VERIFICATION_CODE
    if bypass is not None and bypass.startswith("magic") and bypass == code:
        logger.warning("Using magic bypass code for email="+email)
        return True
    redis_cli = get_redis_cli()
    key = f"chafan:verification-code:{email}"
    value = redis_cli.get(key)
    if value is None:
        return False
    if value != code:
        return False
    redis_cli.delete(key)
    return True

async def register_digit_verification_code(email:str, code:str) -> None:
    redis_cli = get_redis_cli()
    key = f"chafan:verification-code:{email}"
    redis_cli.delete(key)
    redis_cli.set(key, code)
    redis_cli.expire(
        key, time=datetime.timedelta(hours=settings.EMAIL_SIGNUP_CODE_EXPIRE_HOURS)
    )
    #logger.info("Register verification code")



def create_digit_verification_code(length:int) -> str:
    return "".join([str(random.randint(0, 9)) for _ in range(length)])

def create_access_token(
    subject: Union[str, Any], expires_delta: Optional[datetime.timedelta] = None
) -> str:
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(
        to_encode, unwrap(settings.SECRET_KEY), algorithm=ALGORITHM
    )
    return encoded_jwt


def verify_password(plain_password: SecretStr, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password.get_secret_value(), hashed_password)


def get_password_hash(password: SecretStr) -> str:
    return pwd_context.hash(password.get_secret_value())


def generate_password_reset_token(email: CaseInsensitiveEmailStr) -> str:
    delta = datetime.timedelta(hours=settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS)
    now = datetime.datetime.utcnow()
    expires = now + delta
    encoded_jwt = jwt.encode(
        {"exp": expires, "nbf": now, "email": str(email)},
        unwrap(settings.SECRET_KEY),
        algorithm="HS256",
    )
    return encoded_jwt


def check_token_validity_impl(token: str) -> bool:
    try:
        jwt.decode(token, unwrap(settings.SECRET_KEY), algorithms=["HS256"])
        return True
    except Exception:
        return False


def verify_password_reset_token(token: str) -> Optional[str]:
    try:
        decoded_token = jwt.decode(
            token, unwrap(settings.SECRET_KEY), algorithms=["HS256"]
        )
        return decoded_token["email"]
    except Exception:
        return None

