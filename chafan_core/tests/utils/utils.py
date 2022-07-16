import random
import string
from typing import Dict

import requests
from pydantic.types import SecretStr

from chafan_core.utils.base import unwrap
from chafan_core.app.config import settings
from chafan_core.utils.validators import CaseInsensitiveEmailStr, StrippedNonEmptyBasicStr

EMAIL_TEST_USER = CaseInsensitiveEmailStr("test@example.com")
EMAIL_TEST_MODERATOR = CaseInsensitiveEmailStr("mod@example.com")


def random_short_lower_string() -> StrippedNonEmptyBasicStr:
    return StrippedNonEmptyBasicStr(
        "".join(random.choices(string.ascii_lowercase, k=4))
    )


def random_lower_string() -> str:
    return "".join(random.choices(string.ascii_lowercase, k=32))


def random_password() -> SecretStr:
    return SecretStr(random_lower_string())


def random_email() -> CaseInsensitiveEmailStr:
    return CaseInsensitiveEmailStr(
        f"{random_lower_string()}@{random_lower_string()}.com"
    )


def get_superuser_token_headers(client: requests.Session) -> Dict[str, str]:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": unwrap(settings.FIRST_SUPERUSER_PASSWORD).get_secret_value(),
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    assert r.ok, r.json()
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers
