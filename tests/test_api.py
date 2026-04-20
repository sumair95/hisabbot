"""Smoke tests for HTTP endpoints using FastAPI TestClient (in-process)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "kirana-bookkeeper"


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    # In test environment the config is empty, so missing_config will be non-empty
    assert "missing_config" in body


def test_webhook_verify_ok():
    # Default verify token is 'change-me' when nothing is set
    r = client.get(
        "/webhook/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "abc123",
            "hub.verify_token": "change-me",
        },
    )
    assert r.status_code == 200
    assert r.text == "abc123"


def test_webhook_verify_bad_token():
    r = client.get(
        "/webhook/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "abc123",
            "hub.verify_token": "WRONG",
        },
    )
    assert r.status_code == 403


def test_admin_unauthorized():
    r = client.post("/admin/run-daily-summary")
    assert r.status_code == 401
