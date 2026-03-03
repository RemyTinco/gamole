"""Regression tests for POST /api/teams/sync.

Ensures the endpoint accepts requests with no body, empty body, and a full body
without returning 422. The actual Linear API call and DB are mocked so tests
run without PostgreSQL.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_session
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    token = create_session("test-user-id", "test-workspace-id")
    return {"Authorization": f"Bearer {token}"}


# Fake Linear GraphQL response with two teams
_LINEAR_TEAMS_RESPONSE = {
    "data": {
        "teams": {
            "nodes": [
                {"id": "team-uuid-1", "name": "Backend"},
                {"id": "team-uuid-2", "name": "Frontend"},
            ]
        }
    }
}


def _mock_httpx_client(linear_response=None):
    """Return a mock for httpx.AsyncClient context manager with a fake Linear response."""
    response = MagicMock()
    response.json.return_value = linear_response or _LINEAR_TEAMS_RESPONSE
    response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    return mock_client


def _mock_db_session():
    """Return an async generator that yields a mock DB session."""
    session = AsyncMock()
    # session.execute returns a result with scalar_one_or_none() -> None (no existing team)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    @asynccontextmanager
    async def _gen():
        yield session

    # get_session is an async generator, so we need to make it behave like one
    async def fake_get_session():
        yield session

    return fake_get_session


class TestSyncTeamsEndpoint:
    """POST /api/teams/sync regression tests."""

    def test_sync_no_body(self, client, auth_headers):
        """Regression: POST with no body must NOT return 422."""
        with (
            patch("app.config.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=_mock_httpx_client()),
            patch("app.routes.teams.get_session", _mock_db_session()),
        ):
            mock_settings.linear_api_token = "lin_api_test"
            resp = client.post("/api/teams/sync", headers=auth_headers)
        assert resp.status_code != 422, f"Got 422 — body should be optional. Detail: {resp.text}"
        assert resp.status_code == 200

    def test_sync_empty_json_body(self, client, auth_headers):
        """POST with empty JSON body {} should work."""
        with (
            patch("app.config.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=_mock_httpx_client()),
            patch("app.routes.teams.get_session", _mock_db_session()),
        ):
            mock_settings.linear_api_token = "lin_api_test"
            resp = client.post("/api/teams/sync", headers=auth_headers, json={})
        assert resp.status_code != 422, f"Got 422 — empty body should be valid. Detail: {resp.text}"
        assert resp.status_code == 200

    def test_sync_with_token_in_body(self, client, auth_headers):
        """POST with explicit token should use it instead of server config."""
        with (
            patch("httpx.AsyncClient", return_value=_mock_httpx_client()),
            patch("app.routes.teams.get_session", _mock_db_session()),
        ):
            resp = client.post(
                "/api/teams/sync",
                headers=auth_headers,
                json={"token": "lin_api_custom"},
            )
        assert resp.status_code != 422, f"Got 422 — valid body rejected. Detail: {resp.text}"
        assert resp.status_code == 200

    def test_sync_with_descriptions(self, client, auth_headers):
        """POST with descriptions map should apply them to synced teams."""
        with (
            patch("app.config.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=_mock_httpx_client()),
            patch("app.routes.teams.get_session", _mock_db_session()),
        ):
            mock_settings.linear_api_token = "lin_api_test"
            resp = client.post(
                "/api/teams/sync",
                headers=auth_headers,
                json={"descriptions": {"Backend": "Core API services"}},
            )
        assert resp.status_code != 422
        data = resp.json()
        assert data["ok"] is True
        assert data["total"] == 2

    def test_sync_requires_auth(self, client):
        """Must return 401 without auth header."""
        resp = client.post("/api/teams/sync")
        assert resp.status_code == 401

    def test_sync_no_token_available(self, client, auth_headers):
        """Returns 400 when no token is provided and none configured."""
        with patch("app.config.settings") as mock_settings:
            mock_settings.linear_api_token = ""
            resp = client.post("/api/teams/sync", headers=auth_headers)
        assert resp.status_code == 400
        assert "token" in resp.json()["detail"].lower()
