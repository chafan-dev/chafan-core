from fastapi.testclient import TestClient

from chafan_core.app.common import (
    check_token_validity_impl,
    generate_password_reset_token,
)
from chafan_core.app.config import settings
from chafan_core.utils.base import unwrap


def test_get_access_token(client: TestClient) -> None:
    login_data = {
        "username": unwrap(settings.FIRST_SUPERUSER),
        "password": unwrap(settings.FIRST_SUPERUSER_PASSWORD).get_secret_value(),
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    assert r.status_code == 200
    assert "access_token" in tokens
    assert tokens["access_token"]


def test_reset_password_verify(client: TestClient) -> None:
    reset_token = generate_password_reset_token(email=unwrap(settings.FIRST_SUPERUSER))
    assert check_token_validity_impl(reset_token), reset_token

    r = client.post(
        f"{settings.API_V1_STR}/check-token-validity/", data={"token": reset_token}
    )
    response = r.json()
    assert r.status_code == 200
    assert response["success"], response["msg"]
