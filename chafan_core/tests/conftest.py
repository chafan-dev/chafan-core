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
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from chafan_core.app.main import app
from chafan_core.db.session import SessionLocal


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


