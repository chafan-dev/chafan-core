import datetime
from typing import Any, Optional, Union

from jose import jwt
from passlib.context import CryptContext  # type: ignore
from pydantic.types import SecretStr

from chafan_core.utils.validators import CaseInsensitiveEmailStr
from chafan_core.app.config import settings
from chafan_core.utils.base import unwrap

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


ALGORITHM = "HS256"


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

