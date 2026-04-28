import pytest
from fastapi import HTTPException
from pydantic.types import SecretStr

from chafan_core.utils.validators import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    check_password,
    validate_password,
)


def _pw(s: str) -> SecretStr:
    return SecretStr(s)


def test_validate_password_accepts_min_length():
    validate_password(_pw("a" * MIN_PASSWORD_LENGTH))


def test_validate_password_accepts_max_length():
    validate_password(_pw("a" * MAX_PASSWORD_LENGTH))


def test_validate_password_rejects_too_short():
    with pytest.raises(ValueError):
        validate_password(_pw("a" * (MIN_PASSWORD_LENGTH - 1)))


def test_validate_password_rejects_too_long():
    with pytest.raises(ValueError):
        validate_password(_pw("a" * (MAX_PASSWORD_LENGTH + 1)))


def test_validate_password_accepts_non_ascii():
    validate_password(_pw("密码密码" + "a" * (MIN_PASSWORD_LENGTH - 4)))


def test_validate_password_rejects_multibyte_overflow():
    # Each "密" is 3 bytes in utf-8; 25 of them = 75 bytes, exceeds the cap
    # even though character count is only 25.
    with pytest.raises(ValueError):
        validate_password(_pw("密" * 25))


def test_check_password_raises_http_on_invalid():
    with pytest.raises(HTTPException):
        check_password(_pw("short"))


def test_check_password_silent_on_valid():
    check_password(_pw("a" * MIN_PASSWORD_LENGTH))
