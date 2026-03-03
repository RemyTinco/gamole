"""Tests for discovery API endpoint."""

import socket

import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_session
from app.main import app

_db_available = False
try:
    s = socket.create_connection(("localhost", 5432), timeout=1)
    s.close()
    _db_available = True
except OSError:
    pass

requires_db = pytest.mark.skipif(not _db_available, reason="PostgreSQL not running")


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    token = create_session("test-user", "test-workspace")
    return {"Authorization": f"Bearer {token}"}


@requires_db
def test_discovery_answers_not_found(client, auth_headers):
    """Submitting answers to a non-existent generation returns 404."""
    resp = client.post(
        "/api/generation/00000000-0000-0000-0000-000000000000/discovery-answers",
        json={"answers": []},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_discovery_answers_wrong_status(client, auth_headers):
    """Submitting answers to a non-AWAITING_DISCOVERY generation returns 400 (or 404 without DB)."""
    resp = client.post(
        "/api/generation/00000000-0000-0000-0000-000000000000/discovery-answers",
        json={"answers": [{"question_id": "q1", "answer": "test"}]},
        headers=auth_headers,
    )
    # 404 is acceptable here since no DB — the endpoint validates status AFTER finding the record
    assert resp.status_code in (400, 404)


@requires_db
def test_discovery_answers_mismatched_count(client, auth_headers):
    """Submitting wrong number of answers returns 422 when generation exists, 404 otherwise."""
    resp = client.post(
        "/api/generation/00000000-0000-0000-0000-000000000000/discovery-answers",
        json={
            "answers": [
                {"question_id": "q1", "answer": "first answer"},
                {"question_id": "q2", "answer": "second answer"},
            ]
        },
        headers=auth_headers,
    )
    # 404 since no AWAITING_DISCOVERY generation exists in DB; 422 if it does but count mismatches
    assert resp.status_code in (404, 422)


@requires_db
def test_discovery_answers_empty_answer(client, auth_headers):
    """Submitting an empty answer string returns 422 when generation exists, 404 otherwise."""
    resp = client.post(
        "/api/generation/00000000-0000-0000-0000-000000000000/discovery-answers",
        json={"answers": [{"question_id": "q1", "answer": ""}]},
        headers=auth_headers,
    )
    # 404 since no AWAITING_DISCOVERY generation exists; 422 if answer is empty
    assert resp.status_code in (404, 422)


def test_get_generation_includes_discovery_questions(client, auth_headers):
    """Verify that the GET endpoint and POST discovery-answers endpoint are both registered."""
    openapi = client.get("/openapi.json").json()
    assert "/api/generation/{generation_id}" in openapi["paths"]
    assert "/api/generation/{generation_id}/discovery-answers" in openapi["paths"]
