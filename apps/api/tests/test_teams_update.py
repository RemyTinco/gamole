"""Regression tests for PUT /api/teams/{team_id}.

Ensures the endpoint correctly updates team fields and uses timezone-naive
datetimes compatible with asyncpg's TIMESTAMP WITHOUT TIME ZONE columns.
The DB is mocked so tests run without PostgreSQL.
"""

import uuid
from datetime import datetime
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


def _make_mock_team(**overrides):
    """Create a mock LinearTeam with sensible defaults."""
    team = MagicMock()
    team.id = overrides.get("id", uuid.uuid4())
    team.linear_id = overrides.get("linear_id", "lin-test-123")
    team.name = overrides.get("name", "Backend")
    team.description = overrides.get("description", "Handles backend services")
    team.default_state_id = overrides.get("default_state_id", None)
    team.default_labels = overrides.get("default_labels", None)
    team.created_at = overrides.get("created_at", datetime(2026, 1, 1, 12, 0, 0))
    team.updated_at = overrides.get("updated_at", datetime(2026, 1, 1, 12, 0, 0))
    return team


def _mock_db_session(mock_team=None):
    """Return an async generator that yields a mock DB session.

    If mock_team is provided, session.get() returns it.
    """
    session = AsyncMock()
    session.get.return_value = mock_team

    async def fake_get_session():
        yield session

    return fake_get_session, session


class TestUpdateTeamEndpoint:
    """PUT /api/teams/{team_id} regression tests."""

    def test_update_description(self, client, auth_headers):
        """Basic description update should return 200."""
        team = _make_mock_team()
        fake_session, session = _mock_db_session(team)

        with patch("app.routes.teams.get_session", fake_session):
            resp = client.put(
                f"/api/teams/{team.id}",
                headers=auth_headers,
                json={"description": "New description"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "New description"
        assert data["name"] == "Backend"

    def test_update_sets_naive_utc_datetime(self, client, auth_headers):
        """Regression: updated_at must be timezone-naive to avoid asyncpg
        'can't subtract offset-naive and offset-aware datetimes' error
        with TIMESTAMP WITHOUT TIME ZONE columns."""
        team = _make_mock_team()
        fake_session, session = _mock_db_session(team)

        with patch("app.routes.teams.get_session", fake_session):
            client.put(
                f"/api/teams/{team.id}",
                headers=auth_headers,
                json={"description": "Updated"},
            )

        # The key assertion: updated_at must be naive (no tzinfo)
        assert team.updated_at.tzinfo is None, (
            f"updated_at has tzinfo={team.updated_at.tzinfo!r} — "
            "asyncpg rejects tz-aware datetimes for TIMESTAMP WITHOUT TIME ZONE columns"
        )

    def test_update_default_state_id(self, client, auth_headers):
        """Updating defaultStateId via alias should work."""
        team = _make_mock_team()
        fake_session, _ = _mock_db_session(team)

        with patch("app.routes.teams.get_session", fake_session):
            resp = client.put(
                f"/api/teams/{team.id}",
                headers=auth_headers,
                json={"defaultStateId": "state-abc"},
            )

        assert resp.status_code == 200
        assert team.default_state_id == "state-abc"

    def test_update_default_labels(self, client, auth_headers):
        """Updating defaultLabels via alias should work."""
        team = _make_mock_team()
        fake_session, _ = _mock_db_session(team)

        with patch("app.routes.teams.get_session", fake_session):
            resp = client.put(
                f"/api/teams/{team.id}",
                headers=auth_headers,
                json={"defaultLabels": ["bug", "urgent"]},
            )

        assert resp.status_code == 200
        assert team.default_labels == ["bug", "urgent"]

    def test_update_team_not_found(self, client, auth_headers):
        """PUT with unknown UUID should return 404."""
        fake_session, _ = _mock_db_session(None)  # session.get returns None

        with patch("app.routes.teams.get_session", fake_session):
            resp = client.put(
                f"/api/teams/{uuid.uuid4()}",
                headers=auth_headers,
                json={"description": "Doesn't matter"},
            )

        assert resp.status_code == 404

    def test_update_empty_body(self, client, auth_headers):
        """PUT with empty body should still succeed (no fields updated)."""
        team = _make_mock_team()
        fake_session, _ = _mock_db_session(team)

        with patch("app.routes.teams.get_session", fake_session):
            resp = client.put(
                f"/api/teams/{team.id}",
                headers=auth_headers,
                json={},
            )

        assert resp.status_code == 200

    def test_update_requires_auth(self, client):
        """PUT without auth header should return 401."""
        resp = client.put(f"/api/teams/{uuid.uuid4()}", json={"description": "test"})
        assert resp.status_code == 401
