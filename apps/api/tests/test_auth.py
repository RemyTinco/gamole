"""Auth tests."""

import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_session, validate_session
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_create_and_validate_session():
    token = create_session("user-123", "workspace-456")
    assert isinstance(token, str)
    assert len(token) > 10

    payload = validate_session(token)
    assert payload["userId"] == "user-123"
    assert payload["workspaceId"] == "workspace-456"


def test_validate_invalid_token():
    with pytest.raises(ValueError):
        validate_session("invalid-token")


def test_protected_route_without_auth(client):
    response = client.get("/api/generation")
    assert response.status_code == 401


def test_protected_route_with_auth(client):
    token = create_session("user-123")
    response = client.get("/api/generation", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_protected_route_with_bad_token(client):
    response = client.get("/api/generation", headers={"Authorization": "Bearer bad"})
    assert response.status_code == 401
