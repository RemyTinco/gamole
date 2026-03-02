"""Shared test fixtures."""

import os
import socket

# Set DATABASE_URL before any imports that create the engine
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:gamole_dev@localhost:5432/gamole")
os.environ.setdefault("SESSION_SECRET", "test-secret-key-minimum-32-chars-long")

import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_session
from app.main import app


def _postgres_available() -> bool:
    try:
        s = socket.create_connection(("localhost", 5432), timeout=1)
        s.close()
        return True
    except OSError:
        return False


_db_available = _postgres_available()

requires_db = pytest.mark.skipif(
    not _db_available,
    reason="PostgreSQL not running on localhost:5432",
)


def pytest_configure(config):
    config.addinivalue_line("markers", "requires_db: skip if no PostgreSQL")


@pytest.fixture(autouse=True)
def _reset_db_pool():
    """Reset the async engine pool between tests to avoid cross-test connection issues."""
    yield
    try:
        import asyncio

        from gamole_db.session import engine

        loop = asyncio.new_event_loop()
        loop.run_until_complete(engine.dispose())
        loop.close()
    except Exception:
        pass


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_token():
    return create_session("test-user-id", "test-workspace-id")


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}
