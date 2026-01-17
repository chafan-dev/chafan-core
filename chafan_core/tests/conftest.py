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


# =============================================================================
# Core Fixtures - Database, Client, Authentication
# =============================================================================

@pytest.fixture(scope="session")
def db() -> Generator[Session, None, None]:
    """
    Database session using real PostgreSQL (configured via env.ci).
    Scope: session - shared across all tests.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """
    FastAPI test client for making HTTP requests.
    Uses real Redis for caching (configured via env.ci).
    Scope: module - one client per test module.
    """
    with TestClient(app) as test_client:
        yield test_client


# =============================================================================
# User Authentication Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> Dict[str, str]:
    """Authentication headers for superuser (admin)."""
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> Dict[str, str]:
    """Authentication headers for normal test user."""
    import asyncio
    return asyncio.run(authentication_token_from_email(
        client=client, email=EMAIL_TEST_USER, db=db
    ))


@pytest.fixture(scope="module")
def normal_user_id(client: TestClient, normal_user_token_headers: dict) -> int:
    """Normal user's database ID."""
    return client.get(
        f"{settings.API_V1_STR}/me", headers=normal_user_token_headers
    ).json()["id"]


@pytest.fixture(scope="module")
def normal_user_uuid(client: TestClient, normal_user_token_headers: dict) -> str:
    """Normal user's UUID."""
    return client.get(
        f"{settings.API_V1_STR}/me", headers=normal_user_token_headers
    ).json()["uuid"]


@pytest.fixture(scope="module")
def moderator_user_token_headers(client: TestClient, db: Session) -> Dict[str, str]:
    """Authentication headers for moderator test user."""
    import asyncio
    return asyncio.run(authentication_token_from_email(
        client=client, email=EMAIL_TEST_MODERATOR, db=db
    ))


@pytest.fixture(scope="module")
def moderator_user_id(client: TestClient, moderator_user_token_headers: dict) -> int:
    """Moderator user's database ID."""
    return client.get(
        f"{settings.API_V1_STR}/me", headers=moderator_user_token_headers
    ).json()["id"]


@pytest.fixture(scope="module")
def moderator_user_uuid(client: TestClient, moderator_user_token_headers: dict) -> str:
    """Moderator user's UUID."""
    return client.get(
        f"{settings.API_V1_STR}/me", headers=moderator_user_token_headers
    ).json()["uuid"]


# =============================================================================
# Helper Function - Reduce Duplication
# =============================================================================

def ensure_user_in_site(
    client: TestClient,
    db: Session,
    user_id: int,
    user_uuid: str,
    site_uuid: str,
    superuser_token_headers: dict,
) -> None:
    """
    Ensure a user is a member of a site. If not, invite them.
    This helper reduces duplication across fixtures.
    """
    db.expire_all()  # Clear cache to get fresh data from database
    site = crud.site.get_by_uuid(db, uuid=site_uuid)
    assert site is not None, f"Site {site_uuid} not found"

    profile = crud.profile.get_by_user_and_site(
        db, owner_id=user_id, site_id=site.id
    )

    if not profile:
        r = client.post(
            f"{settings.API_V1_STR}/users/invite",
            headers=superuser_token_headers,
            json={"site_uuid": site_uuid, "user_uuid": user_uuid},
        )
        assert r.status_code == 200, f"Failed to invite user: {r.json()}"


# =============================================================================
# Test Site Fixture
# =============================================================================

@pytest.fixture(scope="module")
def example_site_uuid(
    client: TestClient,
    superuser_token_headers: dict,
    moderator_user_uuid: str,
) -> str:
    """
    Create a test site with moderator assigned.
    Scope: module - one site per test module.
    """
    # Create site
    r = client.post(
        f"{settings.API_V1_STR}/sites/",
        headers=superuser_token_headers,
        json={
            "name": f"Test Site ({random_short_lower_string()})",
            "description": "Automated test site",
            "subdomain": f"test_{random_short_lower_string()}",
            "permission_type": "private",
        },
    )
    r.raise_for_status()
    site_uuid = r.json()["created_site"]["uuid"]

    # Assign moderator
    r = client.put(
        f"{settings.API_V1_STR}/sites/{site_uuid}/config",
        json={"moderator_uuid": moderator_user_uuid},
        headers=superuser_token_headers,
    )
    assert r.status_code == 200, f"Failed to set moderator: {r.json()}"

    return site_uuid


# =============================================================================
# Helper Function - Ensure Coin Balance
# =============================================================================

def ensure_user_has_coins(db: Session, user_id: int, coins: int = 100) -> None:
    """
    Ensure a user has sufficient coins for testing.
    This directly updates the database to give users coins.

    Args:
        db: Database session
        user_id: User's database ID
        coins: Minimum number of coins to ensure (default: 100)
    """
    db.expire_all()  # Clear cache to get fresh data from database
    user = crud.user.get(db, id=user_id)
    assert user is not None, f"User {user_id} not found"

    if user.remaining_coins < coins:
        crud.user.update(db, db_obj=user, obj_in={"remaining_coins": coins})


# =============================================================================
# Test Content Fixtures
# =============================================================================

# =============================================================================
# Article Column and Article Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def example_article_column_uuid(
    client: TestClient,
    normal_user_token_headers: dict,
) -> str:
    """
    Create a test article column owned by normal_user.
    Scope: module - one article column per test module.
    """
    r = client.post(
        f"{settings.API_V1_STR}/article-columns/",
        headers=normal_user_token_headers,
        json={
            "name": f"Test Column ({random_short_lower_string()})",
            "description": "Automated test article column",
        },
    )
    r.raise_for_status()
    return r.json()["uuid"]


@pytest.fixture(scope="module")
def example_article_uuid(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_id: int,
    example_article_column_uuid: str,
) -> str:
    """
    Create a test article authored by normal_user.
    Scope: module - one article per test module.
    """
    from chafan_core.utils.base import get_uuid

    ensure_user_has_coins(db, normal_user_id, coins=100)

    r = client.post(
        f"{settings.API_V1_STR}/articles/",
        headers=normal_user_token_headers,
        json={
            "title": f"Test Article ({random_short_lower_string()})",
            "content": {
                "source": "This is test article content.",
                "editor": "tiptap",
            },
            "article_column_uuid": example_article_column_uuid,
            "is_published": True,
            "writing_session_uuid": get_uuid(),
            "visibility": "anyone",
        },
    )
    r.raise_for_status()
    return r.json()["uuid"]


@pytest.fixture(scope="module")
def normal_user_authored_question_uuid(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    normal_user_id: int,
    normal_user_uuid: str,
    example_site_uuid: str,
) -> str:
    """
    Create a test question authored by normal_user.
    Ensures user is a site member first.
    """
    # Ensure user is in site
    ensure_user_in_site(
        client, db, normal_user_id, normal_user_uuid,
        example_site_uuid, superuser_token_headers
    )

    # Create question
    r = client.post(
        f"{settings.API_V1_STR}/questions/",
        headers=normal_user_token_headers,
        json={
            "site_uuid": example_site_uuid,
            "title": f"Test Question ({random_short_lower_string()})",
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
    normal_user_id: int,
    normal_user_uuid: str,
    example_site_uuid: str,
) -> str:
    """
    Create a test submission authored by normal_user.
    Ensures user is a site member first.
    """
    # Ensure user is in site
    ensure_user_in_site(
        client, db, normal_user_id, normal_user_uuid,
        example_site_uuid, superuser_token_headers
    )

    # Create submission
    r = client.post(
        f"{settings.API_V1_STR}/submissions/",
        headers=normal_user_token_headers,
        json={
            "site_uuid": example_site_uuid,
            "title": f"Test Submission ({random_short_lower_string()})",
            "url": "https://example.com/test-submission",
        },
    )
    r.raise_for_status()
    return r.json()["uuid"]
