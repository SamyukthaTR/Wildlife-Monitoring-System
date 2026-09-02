"""Fixtures for the integration test suite (backend/tests/test_api_*.py).

Unlike the pure-function tests, these need a live Postgres+PostGIS database
-- TEST_DATABASE_URL if set, otherwise DATABASE_URL with its database name
suffixed "_test". See docs/milestone4.md for how to create it. Every fixture
here is scoped to keep the existing pure-function suite (test_biodiversity.py
etc.) running with zero database dependency, exactly as documented.
"""

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base
from app.core.deps import get_db
from app.core.rate_limit import limiter
from app.main import app

# Import every model module so Base.metadata knows about all tables before
# create_all runs -- each module registers its tables on import.
from app.modules.users import models as _users_models  # noqa: F401
from app.modules.monitoring import models as _monitoring_models  # noqa: F401
from app.modules.observations import models as _observations_models  # noqa: F401
from app.modules.analysis import models as _analysis_models  # noqa: F401
from app.modules.species import models as _species_models  # noqa: F401
from app.modules.habitat import models as _habitat_models  # noqa: F401

TEST_DATABASE_URL = settings.TEST_DATABASE_URL or re.sub(
    r"/([^/]+)$", r"/\1_test", settings.DATABASE_URL
)

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    # Every test uses the same TestClient host, so without this the
    # login/register rate limits (shared in-memory storage) would bleed
    # across tests and fail them with 429s unrelated to what they're testing.
    limiter._storage.reset()
    yield


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register_and_login(client: TestClient, email: str, role: str, password: str = "TestPass123!") -> str:
    """Registers a user with the given role and returns a bearer access token."""
    resp = client.post("/auth/register", json={
        "name": email.split("@")[0],
        "email": email,
        "password": password,
        "role": role,
    })
    assert resp.status_code == 201, resp.text
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(client):
    def _make(role: str, email: str | None = None) -> dict:
        email = email or f"{role.lower().replace(' ', '-')}@wildlifetest.dev"
        token = register_and_login(client, email, role)
        return {"Authorization": f"Bearer {token}"}
    return _make
