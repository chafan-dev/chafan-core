from datetime import datetime, timedelta
from typing import Any, Optional, Union

from jose import jwt
from passlib.context import CryptContext  # type: ignore
from pydantic.types import SecretStr

from chafan_core.app.config import settings
from chafan_core.utils.base import unwrap

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


ALGORITHM = "HS256"


def create_access_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
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
