# Set Mock env config (only if not already set)
import os
mock_env = {
"DATABASE_URL" : "stub_url",
"REDIS_URL" : "stub_url",
"SERVER_HOST" : "stub_server_host",
}
for k,v in mock_env.items():
    if k not in os.environ:
        os.environ[k] = v

# End of Mock env config

from chafan_core.app.config import settings

import pytest
from typing import Dict, Generator
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from chafan_core.app.main import app
from chafan_core.app import crud
from chafan_core.db.session import SessionLocal
from chafan_core.tests.utils.user import authentication_token_from_email
from chafan_core.tests.utils.utils import (
    EMAIL_TEST_USER,
    EMAIL_TEST_MODERATOR,
    get_superuser_token_headers,
    random_short_lower_string,
    random_lower_string,
)


@pytest.fixture(scope="session")
def db() -> Generator[Session, None, None]:
    """
    Create a fresh database session for testing.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """
    Create a test client for the FastAPI app.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> Dict[str, str]:
    """
    Get authentication headers for the superuser.
    """
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> Dict[str, str]:
    """
    Get authentication headers for a normal user.
    """
    import asyncio
    return asyncio.run(authentication_token_from_email(
        client=client, email=EMAIL_TEST_USER, db=db
    ))


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
    import asyncio
    return asyncio.run(authentication_token_from_email(
        client=client, email=EMAIL_TEST_MODERATOR, db=db
    ))


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
def example_site_uuid(
    client: TestClient, superuser_token_headers: dict, moderator_user_uuid: str
) -> str:
    r = client.post(
        f"{settings.API_V1_STR}/sites/",
        headers=superuser_token_headers,
        json={
            "name": f"Demo ({random_short_lower_string()})",
            "description": "Demo Site",
            "subdomain": f"demo_{random_short_lower_string()}",
            "permission_type": "private",
        },
    )
    r.raise_for_status()
    site_uuid = r.json()["created_site"]["uuid"]
    r = client.put(
        f"{settings.API_V1_STR}/sites/{site_uuid}/config",
        json={
            "moderator_uuid": moderator_user_uuid,
        },
        headers=superuser_token_headers,
    )
    assert r.status_code == 200, (r.status_code, r.json())
    return site_uuid


@pytest.fixture(scope="module")
def normal_user_authored_question_uuid(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
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
            f"{settings.API_V1_STR}/users/invite",
            headers=superuser_token_headers,
            json={"site_uuid": example_site_uuid, "user_uuid": normal_user_uuid},
        )
        assert r.status_code == 200, (r.status_code, r.json())

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


@pytest.fixture(scope="module")
def example_submission_uuid(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    normal_user_uuid: str,
    normal_user_id: int,
    example_site_uuid: str,
) -> str:
    """Create a test submission for use in tests."""
    # Ensure user is member of the site
    site = crud.site.get_by_uuid(db, uuid=example_site_uuid)
    assert site is not None
    profile = crud.profile.get_by_user_and_site(
        db, owner_id=normal_user_id, site_id=site.id
    )
    if not profile:
        r = client.post(
            f"{settings.API_V1_STR}/users/invite",
            headers=superuser_token_headers,
            json={"site_uuid": example_site_uuid, "user_uuid": normal_user_uuid},
        )
        assert r.status_code == 200, (r.status_code, r.json())

    # Create submission
    r = client.post(
        f"{settings.API_V1_STR}/submissions/",
        headers=normal_user_token_headers,
        json={
            "site_uuid": example_site_uuid,
            "title": f"Test Submission ({random_short_lower_string()})",
            "url": "https://example.com/test-submission",
            "desc": {
                "source": "Test description for submission",
                "rendered_text": "Test description for submission",
                "editor": "markdown",
            }
        },
    )
    r.raise_for_status()
    return r.json()["uuid"]


