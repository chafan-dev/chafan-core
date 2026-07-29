from fastapi.testclient import TestClient

from chafan_core.app.security import (
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


def test_password_recovery_is_rate_limited(client: TestClient, monkeypatch) -> None:
    """`@limiter.limit` must sit below `@router.post`, or it never applies.

    Decorators apply bottom-up: with the limiter on top, `router.post` registers
    the *undecorated* function and the rate-limited wrapper is never routed.
    That left POST /password-recovery/{email} open to unauthenticated
    password-reset email flooding against any address.

    A second, independent defect had to be fixed alongside the decorator
    order: the handler needs a `response: Response` parameter, because the
    limiter runs with `headers_enabled=True` and slowapi injects the
    `X-RateLimit-*` headers into it. Swapping the decorators alone turns the
    inert limit into a 500 on every call, which this test also catches.

    `client_ip` honours x-forwarded-for, so each run gets its own bucket rather
    than depending on Redis state left by earlier tests.
    """
    from chafan_core.app.services import auth as auth_service

    sent: list = []
    monkeypatch.setattr(
        auth_service,
        "send_reset_password_email",
        lambda **kwargs: sent.append(kwargs),
    )

    email = unwrap(settings.FIRST_SUPERUSER)
    headers = {"X-Forwarded-For": f"198.51.100.{len(email) % 200 + 1}"}
    url = f"{settings.API_V1_STR}/password-recovery/{email}"

    first = client.post(url, headers=headers)
    assert first.status_code == 200, first.text

    second = client.post(url, headers=headers)
    assert second.status_code == 429, (
        f"second call returned {second.status_code}, not 429 -- the rate limit "
        f"is inert; check that @limiter.limit sits below @router.post"
    )

    assert len(sent) == 1, "the rate-limited call must not send a second email"
