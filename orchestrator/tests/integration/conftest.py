"""
Integration test fixtures for the orchestrator.

Required env vars:
    RAZORPAY_API_KEY
    RAZORPAY_API_SECRET
    CLICKHOUSE_HOST
    TEST_DATABASE_URL   — Postgres test DB e.g. postgresql://postgres:postgres@localhost:5432/orchestrator_test

Optional:
    CLICKHOUSE_PORT     (default: 9000)
    CLICKHOUSE_DATABASE (default: default)
    CLICKHOUSE_USER     (default: default)
    CLICKHOUSE_PASSWORD (default: empty)

Setup:
    pip install -e ../connectors   # data-connectors from monorepo
    createdb orchestrator_test     # one-time
"""

import os
import socket
import uuid

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../src/orchestrator/.env"))

# ---------------------------------------------------------------------------
# In-memory secrets store — replaces AWS Secrets Manager in tests
# ---------------------------------------------------------------------------
_secret_store: dict[str, dict[str, str]] = {}


def _mock_put_secret(secret_ref: str, credentials: dict[str, str]) -> None:
    _secret_store[secret_ref] = credentials


def _mock_get_secret(secret_ref: str) -> dict[str, str]:
    if secret_ref not in _secret_store:
        raise RuntimeError(f"Secret not found in test store: {secret_ref}")
    return _secret_store[secret_ref]


@pytest.fixture(scope="session", autouse=True)
def patch_secrets(session_mocker=None):  # type: ignore[no-untyped-def]
    """Monkeypatch secrets module before app import so no AWS calls are made."""
    import orchestrator.secrets as secrets_mod

    secrets_mod.put_secret = _mock_put_secret  # type: ignore[method-assign]
    secrets_mod.get_secret = _mock_get_secret  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Test database
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://localhost:5432/turbocat_db")


@pytest.fixture(scope="session")
def db_engine():
    from orchestrator.models import Base

    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(db_engine) -> Session:  # type: ignore[no-untyped-def]
    TestSession = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = TestSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def app(db_engine):  # type: ignore[no-untyped-def]
    from orchestrator.db import get_db
    from orchestrator.main import app as fastapi_app

    TestSession = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    def override_get_db():  # type: ignore[no-untyped-def]
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    return fastapi_app


@pytest.fixture(scope="session")
def client(app) -> TestClient:  # type: ignore[no-untyped-def]
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Source / destination fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def razorpay_creds() -> dict[str, str]:
    api_key = os.getenv("RAZORPAY_API_KEY")
    api_secret = os.getenv("RAZORPAY_API_SECRET")
    if not api_key or not api_secret:
        pytest.skip("RAZORPAY_API_KEY and RAZORPAY_API_SECRET required")
    return {"api_key": api_key, "api_secret": api_secret}


@pytest.fixture(scope="session")
def clickhouse_config():
    if not os.getenv("CLICKHOUSE_HOST"):
        pytest.skip("CLICKHOUSE_HOST required")
    host = os.getenv("CLICKHOUSE_HOST", "localhost")
    port = int(os.getenv("CLICKHOUSE_PORT", "9000"))
    try:
        with socket.create_connection((host, port), timeout=2):
            pass
    except OSError:
        pytest.skip(f"ClickHouse not reachable at {host}:{port}")

    from data_connectors.destinations.clickhouse.config import ClickHouseConfig

    return ClickHouseConfig()


# ---------------------------------------------------------------------------
# Shared agent fixture
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def test_account_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture(scope="session")
def test_agent(db_engine, test_account_id) -> "Agent":  # type: ignore[name-defined] # noqa: F821
    from sqlalchemy.orm import sessionmaker as sm

    from orchestrator.models import Agent

    session = sm(bind=db_engine)()
    agent = Agent(account_id=test_account_id, status="active")
    session.add(agent)
    session.commit()
    session.refresh(agent)
    session.close()
    return agent
