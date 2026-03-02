"""Health endpoint tests."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "gamole-api"
    assert "timestamp" in data


def test_not_found_returns_json(client):
    response = client.get("/nonexistent")
    assert response.status_code == 404
    assert response.json() == {"error": "Not found"}
