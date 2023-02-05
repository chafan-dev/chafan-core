from typing import Dict

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.config import settings
from chafan_core.app.schemas.user import UserCreate
from chafan_core.tests.utils.utils import (
    EMAIL_TEST_USER,
    random_email,
    random_password,
    random_short_lower_string,
)


def test_get_users_superuser_me(
    client: TestClient, superuser_token_headers: Dict[str, str]
) -> None:
    r = client.get(f"{settings.API_V1_STR}/me", headers=superuser_token_headers)
    current_user = r.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["is_superuser"]
    assert current_user["email"] == settings.FIRST_SUPERUSER


def test_get_users_normal_user_me(
    client: TestClient, normal_user_token_headers: Dict[str, str]
) -> None:
    r = client.get(f"{settings.API_V1_STR}/me", headers=normal_user_token_headers)
    current_user = r.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["is_superuser"] is False
    assert current_user["email"] == EMAIL_TEST_USER


def create_invitation_uuid(client: TestClient) -> str:
    r = client.get(
        f"{settings.API_V1_STR}/invitation-links/daily",
    )
    assert 200 <= r.status_code < 300, r.text
    return r.json()["uuid"]


def get_open_user_account_response(
    client: TestClient, username: str, password: str, invitation_uuid: str
) -> None:
    data = {
        "email": username,
        "password": password,
        "handle": random_short_lower_string(),
        "code": "dev",
        "invitation_link_uuid": invitation_uuid,
    }
    return client.post(
        f"{settings.API_V1_STR}/open-account",
        json=data,
    )


def test_create_user_new_email(client: TestClient, db: Session) -> None:
    invitation_uuid = create_invitation_uuid(client)
    username = random_email()
    password = random_password()
    r = get_open_user_account_response(
        client, username, password.get_secret_value(), invitation_uuid
    )
    assert 200 <= r.status_code < 300, r.text
    created_user = r.json()

    user = crud.user.get_by_email(db, email=username)
    assert user
    assert user.email == created_user["email"]


def test_create_user_existing_username(client: TestClient, db: Session) -> None:
    invitation_uuid = create_invitation_uuid(client)
    username = random_email()
    password = random_password()
    user_in = UserCreate(
        email=username, password=password, handle=random_short_lower_string()
    )
    crud.user.create(db, obj_in=user_in)
    r = get_open_user_account_response(
        client, username, password.get_secret_value(), invitation_uuid
    )
    assert r.status_code == 401
    created_user = r.json()
    assert "_id" not in created_user
