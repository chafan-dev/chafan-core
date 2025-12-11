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
from chafan_core.db.session import SessionLocal
from chafan_core.tests.utils.user import authentication_token_from_email
from chafan_core.tests.utils.utils import EMAIL_TEST_USER, get_superuser_token_headers


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
async def normal_user_token_headers(client: TestClient, db: Session) -> Dict[str, str]:
    """
    Get authentication headers for a normal user.
    """
    return await authentication_token_from_email(
        client=client, email=EMAIL_TEST_USER, db=db
    )


