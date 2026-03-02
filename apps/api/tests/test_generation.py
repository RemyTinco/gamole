"""Tests for generation endpoints."""

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


def test_start_generation(client, auth_headers):
    import time

    import app.routes.generation as gen_module

    resp = client.post("/api/generation", json={"input": "test feature"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["status"] == "running"
    time.sleep(0.5)
    gen_module._active_generation = None


def test_list_generations(client, auth_headers):
    resp = client.get("/api/generation", headers=auth_headers)
    assert resp.status_code == 200
    assert "workflows" in resp.json()


def test_generation_not_found(client, auth_headers):
    resp = client.get("/api/generation/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert resp.status_code == 404


def test_generation_stream_no_auth_required(client):
    openapi = client.get("/openapi.json").json()
    stream_path = "/api/generation/{generation_id}/stream"
    assert stream_path in openapi["paths"]


def test_concurrent_generation_blocked(client, auth_headers):
    import app.routes.generation as gen_module

    gen_module._active_generation = {"id": "fake-running"}
    try:
        resp = client.post("/api/generation", json={"input": "should be blocked"}, headers=auth_headers)
        assert resp.status_code == 409
        assert "already in progress" in resp.json()["detail"]
    finally:
        gen_module._active_generation = None


@requires_db
def test_update_document_not_found(client, auth_headers):
    resp = client.put(
        "/api/generation/00000000-0000-0000-0000-000000000000/document",
        json={"document": "edited text"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@requires_db
def test_finalize_not_found(client, auth_headers):
    resp = client.post(
        "/api/generation/00000000-0000-0000-0000-000000000000/finalize",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@requires_db
def test_feedback_stats_endpoint(client, auth_headers):
    resp = client.get("/api/feedback/stats", headers=auth_headers)
    assert resp.status_code == 200


@requires_db
def test_feedback_not_found(client, auth_headers):
    resp = client.post(
        "/api/feedback/00000000-0000-0000-0000-000000000000",
        json={"edited_stories": [], "notes": "test"},
        headers=auth_headers,
    )
    assert resp.status_code in (404, 500)
