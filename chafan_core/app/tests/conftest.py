from typing import Dict, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import crud
from chafan_core.app.config import settings
from chafan_core.app.db.session import SessionLocal
from chafan_core.app.main import app
from chafan_core.app.tests.utils.user import authentication_token_from_email
from chafan_core.app.tests.utils.utils import (
    EMAIL_TEST_MODERATOR,
    EMAIL_TEST_USER,
    get_superuser_token_headers,
    random_lower_string,
    random_short_lower_string,
)


@pytest.fixture(scope="session")
def db() -> Generator:
    yield SessionLocal()


@pytest.fixture(scope="module")
def client() -> Generator:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> Dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> Dict[str, str]:
    return authentication_token_from_email(client=client, email=EMAIL_TEST_USER, db=db)


@pytest.fixture(scope="module")
def normal_user_id(client: TestClient, normal_user_token_headers: dict) -> int:
    return client.get(
        f"{settings.API_V1_STR}/me", headers=normal_user_token_headers
    ).json()["id"]


@pytest.fixture(scope="module")
def normal_user_uuid(client: TestClient, normal_user_token_headers: dict) -> str:
    return client.get(
        f"{settings.API_V1_STR}/me", headers=normal_user_token_headers
    ).json()["uuid"]


@pytest.fixture(scope="module")
def moderator_user_token_headers(client: TestClient, db: Session) -> Dict[str, str]:
    return authentication_token_from_email(
        client=client, email=EMAIL_TEST_MODERATOR, db=db
    )


@pytest.fixture(scope="module")
def moderator_user_id(client: TestClient, moderator_user_token_headers: dict) -> int:
    return client.get(
        f"{settings.API_V1_STR}/me", headers=moderator_user_token_headers
    ).json()["id"]


@pytest.fixture(scope="module")
def moderator_user_uuid(client: TestClient, moderator_user_token_headers: dict) -> str:
    return client.get(
        f"{settings.API_V1_STR}/me", headers=moderator_user_token_headers
    ).json()["uuid"]


@pytest.fixture(scope="module")
def example_site_uuid(client: TestClient, moderator_user_token_headers: dict) -> str:
    r = client.post(
        f"{settings.API_V1_STR}/sites/",
        headers=moderator_user_token_headers,
        json={
            "name": f"Demo ({random_short_lower_string()})",
            "description": "Demo Site",
            "subdomain": f"demo_{random_short_lower_string()}",
            "permission_type": "private",
        },
    )
    r.raise_for_status()
    return r.json()["created_site"]["uuid"]


@pytest.fixture(scope="module")
def normal_user_authored_question_uuid(
    client: TestClient,
    db: Session,
    moderator_user_token_headers: dict,
    normal_user_token_headers: dict,
    example_site_uuid: str,
    normal_user_id: int,
) -> str:
    site = crud.site.get_by_uuid(db, uuid=example_site_uuid)
    assert site is not None
    profile = crud.profile.get_by_user_and_site(
        db, owner_id=normal_user_id, site_id=site.id
    )
    normal_user_uuid = client.get(
        f"{settings.API_V1_STR}/me", headers=normal_user_token_headers
    ).json()["uuid"]
    if not profile:
        r = client.post(
            f"{settings.API_V1_STR}/profiles/",
            headers=moderator_user_token_headers,
            json={"site_uuid": example_site_uuid, "owner_uuid": normal_user_uuid},
        )
        assert r.ok, r.text

    r = client.post(
        f"{settings.API_V1_STR}/questions/",
        headers=normal_user_token_headers,
        json={
            "site_uuid": example_site_uuid,
            "title": "test question",
            "description": random_lower_string(),
        },
    )
    r.raise_for_status()
    return r.json()["uuid"]
