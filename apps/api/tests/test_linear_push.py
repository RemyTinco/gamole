"""Regression tests for Linear push endpoints.

Ensures the push endpoints accept camelCase/snake_case field names,
handle optional config/token with server-side fallbacks, and reject
truly invalid requests. The actual Linear API call and DB are mocked
so tests run without PostgreSQL.
"""

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


# --- Sample data ---

_VALID_STRUCTURED_OUTPUT = {
    "epics": [
        {
            "epicTitle": "User Authentication",
            "epicDescription": "Implement auth flow",
            "teamName": "Backend",
            "teamReason": "Backend owns auth",
            "stories": [
                {
                    "title": "Login endpoint",
                    "description": "POST /auth/login",
                    "acceptanceCriteria": ["Returns JWT on success"],
                    "assumptions": ["Using HS256"],
                    "technicalNotes": None,
                }
            ],
        }
    ],
    "projectName": "Auth Feature",
    "overallNotes": None,
}

_VALID_STRUCTURED_OUTPUT_SNAKE = {
    "epics": [
        {
            "epic_title": "User Authentication",
            "epic_description": "Implement auth flow",
            "team_name": "Backend",
            "team_reason": "Backend owns auth",
            "stories": [
                {
                    "title": "Login endpoint",
                    "description": "POST /auth/login",
                    "acceptance_criteria": ["Returns JWT on success"],
                    "assumptions": ["Using HS256"],
                    "technical_notes": None,
                }
            ],
        }
    ],
    "project_name": "Auth Feature",
    "overall_notes": None,
}


def _mock_push_to_linear():
    """Return a mock for push_to_linear that returns a valid result."""
    from gamole_types.schemas.linear import (
        CreatedIssueInfo,
        CreatedRelationInfo,
        LinearPushResult,
    )

    return AsyncMock(
        return_value=LinearPushResult(
            createdIssues=[
                CreatedIssueInfo(linearId="id-1", identifier="BACK-1", title="User Auth"),
                CreatedIssueInfo(linearId="id-2", identifier="BACK-2", title="Login endpoint"),
            ],
            createdRelations=[
                CreatedRelationInfo(id="rel-1", type="blocks"),
            ],
            errors=[],
        )
    )


def _mock_db_session_with_workflow(structured_output=None, status="READY_TO_PUSH"):
    """Return an async generator that yields a mock DB session with a fake workflow."""
    import uuid

    wf = MagicMock()
    wf.id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    wf.status = status
    wf.structured_output = structured_output

    session = AsyncMock()
    session.get.return_value = wf
    session.commit = AsyncMock()

    async def fake_get_session():
        yield session

    return fake_get_session, wf


# =============================================================================
# POST /api/linear/push-generation
# =============================================================================


class TestPushGenerationEndpoint:
    """POST /api/linear/push-generation regression tests."""

    def test_push_generation_camelcase_body(self, client, auth_headers):
        """Regression: camelCase generationId must NOT return 422."""
        fake_get_session, _ = _mock_db_session_with_workflow(structured_output=_VALID_STRUCTURED_OUTPUT)
        mock_push = _mock_push_to_linear()

        with (
            patch("app.routes.linear.settings") as mock_settings,
            patch("gamole_db.get_session", fake_get_session),
            patch("gamole_linear.push.push_to_linear", mock_push),
        ):
            mock_settings.linear_api_token = "lin_api_test"
            resp = client.post(
                "/api/linear/push-generation",
                headers=auth_headers,
                json={"generationId": "00000000-0000-0000-0000-000000000001"},
            )
        assert resp.status_code != 422, f"Got 422 — camelCase body rejected. Detail: {resp.text}"
        assert resp.status_code == 200

    def test_push_generation_snake_case_body(self, client, auth_headers):
        """snake_case generation_id should also work (populate_by_name)."""
        fake_get_session, _ = _mock_db_session_with_workflow(structured_output=_VALID_STRUCTURED_OUTPUT)
        mock_push = _mock_push_to_linear()

        with (
            patch("app.routes.linear.settings") as mock_settings,
            patch("gamole_db.get_session", fake_get_session),
            patch("gamole_linear.push.push_to_linear", mock_push),
        ):
            mock_settings.linear_api_token = "lin_api_test"
            resp = client.post(
                "/api/linear/push-generation",
                headers=auth_headers,
                json={"generation_id": "00000000-0000-0000-0000-000000000001"},
            )
        assert resp.status_code != 422, f"Got 422 — snake_case body rejected. Detail: {resp.text}"
        assert resp.status_code == 200

    def test_push_generation_minimal_body(self, client, auth_headers):
        """Only generationId is required — config and token should fall back to defaults."""
        fake_get_session, _ = _mock_db_session_with_workflow(structured_output=_VALID_STRUCTURED_OUTPUT)
        mock_push = _mock_push_to_linear()

        with (
            patch("app.routes.linear.settings") as mock_settings,
            patch("gamole_db.get_session", fake_get_session),
            patch("gamole_linear.push.push_to_linear", mock_push),
        ):
            mock_settings.linear_api_token = "lin_api_test"
            resp = client.post(
                "/api/linear/push-generation",
                headers=auth_headers,
                json={"generationId": "00000000-0000-0000-0000-000000000001"},
            )
        assert resp.status_code == 200, f"Minimal body should work. Detail: {resp.text}"

    def test_push_generation_with_explicit_token(self, client, auth_headers):
        """Explicit token in body should be used."""
        fake_get_session, _ = _mock_db_session_with_workflow(structured_output=_VALID_STRUCTURED_OUTPUT)
        mock_push = _mock_push_to_linear()

        with (
            patch("gamole_db.get_session", fake_get_session),
            patch("gamole_linear.push.push_to_linear", mock_push),
        ):
            resp = client.post(
                "/api/linear/push-generation",
                headers=auth_headers,
                json={
                    "generationId": "00000000-0000-0000-0000-000000000001",
                    "token": "lin_api_custom",
                },
            )
        assert resp.status_code == 200, f"Explicit token should work. Detail: {resp.text}"

    def test_push_generation_with_config(self, client, auth_headers):
        """Config with camelCase fields should be accepted."""
        fake_get_session, _ = _mock_db_session_with_workflow(structured_output=_VALID_STRUCTURED_OUTPUT)
        mock_push = _mock_push_to_linear()

        with (
            patch("app.routes.linear.settings") as mock_settings,
            patch("gamole_db.get_session", fake_get_session),
            patch("gamole_linear.push.push_to_linear", mock_push),
        ):
            mock_settings.linear_api_token = "lin_api_test"
            resp = client.post(
                "/api/linear/push-generation",
                headers=auth_headers,
                json={
                    "generationId": "00000000-0000-0000-0000-000000000001",
                    "config": {"teamId": "team-1", "labels": ["bug"]},
                },
            )
        assert resp.status_code == 200, f"Config with camelCase should work. Detail: {resp.text}"

    def test_push_generation_no_token_returns_400(self, client, auth_headers):
        """Returns 400 when no token provided and none configured."""
        with patch("app.routes.linear.settings") as mock_settings:
            mock_settings.linear_api_token = ""
            resp = client.post(
                "/api/linear/push-generation",
                headers=auth_headers,
                json={"generationId": "00000000-0000-0000-0000-000000000001"},
            )
        assert resp.status_code == 400
        assert "token" in resp.json()["detail"].lower()

    def test_push_generation_requires_auth(self, client):
        """Must return 401 without auth header."""
        resp = client.post(
            "/api/linear/push-generation",
            json={"generationId": "00000000-0000-0000-0000-000000000001"},
        )
        assert resp.status_code == 401

    def test_push_generation_missing_generation_id_returns_422(self, client, auth_headers):
        """Missing generationId should still return 422 — it's required."""
        with patch("app.routes.linear.settings") as mock_settings:
            mock_settings.linear_api_token = "lin_api_test"
            resp = client.post(
                "/api/linear/push-generation",
                headers=auth_headers,
                json={},
            )
        assert resp.status_code == 422


# =============================================================================
# POST /api/linear/validate
# =============================================================================


class TestValidateEndpoint:
    """POST /api/linear/validate regression tests."""

    def test_validate_with_camelcase_output(self, client, auth_headers):
        """camelCase structured output should be accepted."""
        resp = client.post(
            "/api/linear/validate",
            headers=auth_headers,
            json={"output": _VALID_STRUCTURED_OUTPUT},
        )
        assert resp.status_code != 422, f"Got 422 — camelCase output rejected. Detail: {resp.text}"
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["epicCount"] == 1
        assert data["storyCount"] == 1

    def test_validate_with_snake_case_output(self, client, auth_headers):
        """snake_case structured output should also be accepted (populate_by_name)."""
        resp = client.post(
            "/api/linear/validate",
            headers=auth_headers,
            json={"output": _VALID_STRUCTURED_OUTPUT_SNAKE},
        )
        assert resp.status_code != 422, f"Got 422 — snake_case output rejected. Detail: {resp.text}"
        assert resp.status_code == 200

    def test_validate_no_config_uses_default(self, client, auth_headers):
        """Config should be optional with an empty default."""
        resp = client.post(
            "/api/linear/validate",
            headers=auth_headers,
            json={"output": _VALID_STRUCTURED_OUTPUT},
        )
        assert resp.status_code == 200

    def test_validate_missing_output_returns_422(self, client, auth_headers):
        """Missing output should return 422."""
        resp = client.post(
            "/api/linear/validate",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 422


# =============================================================================
# POST /api/linear/push
# =============================================================================


class TestPushEndpoint:
    """POST /api/linear/push regression tests."""

    def test_push_with_camelcase_output(self, client, auth_headers):
        """camelCase structured output should be accepted."""
        mock_push = _mock_push_to_linear()

        with (
            patch("app.routes.linear.settings") as mock_settings,
            patch("gamole_linear.push.push_to_linear", mock_push),
        ):
            mock_settings.linear_api_token = "lin_api_test"
            resp = client.post(
                "/api/linear/push",
                headers=auth_headers,
                json={"output": _VALID_STRUCTURED_OUTPUT},
            )
        assert resp.status_code != 422, f"Got 422 — camelCase output rejected. Detail: {resp.text}"
        assert resp.status_code == 200

    def test_push_with_explicit_token(self, client, auth_headers):
        """Explicit token should be used."""
        mock_push = _mock_push_to_linear()

        with patch("gamole_linear.push.push_to_linear", mock_push):
            resp = client.post(
                "/api/linear/push",
                headers=auth_headers,
                json={
                    "output": _VALID_STRUCTURED_OUTPUT,
                    "token": "lin_api_custom",
                },
            )
        assert resp.status_code == 200

    def test_push_no_token_returns_400(self, client, auth_headers):
        """Returns 400 when no token provided and none configured."""
        with patch("app.routes.linear.settings") as mock_settings:
            mock_settings.linear_api_token = ""
            resp = client.post(
                "/api/linear/push",
                headers=auth_headers,
                json={"output": _VALID_STRUCTURED_OUTPUT},
            )
        assert resp.status_code == 400
        assert "token" in resp.json()["detail"].lower()

    def test_push_requires_auth(self, client):
        """Must return 401 without auth header."""
        resp = client.post(
            "/api/linear/push",
            json={"output": _VALID_STRUCTURED_OUTPUT},
        )
        assert resp.status_code == 401
