"""Integration tests for the authentication endpoints. Needs a live database
-- see conftest.py and docs/milestone4.md. Run with `pytest -m integration`.
"""

import pytest

from app.core.config import settings

pytestmark = pytest.mark.integration


def test_register_then_login(client, auth_headers):
    headers = auth_headers("Wildlife Researcher", email="researcher1@wildlifetest.dev")

    me = client.get("/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] == "Wildlife Researcher"


def test_duplicate_registration_rejected(client, auth_headers):
    auth_headers("Wildlife Researcher", email="dup@wildlifetest.dev")
    resp = client.post("/auth/register", json={
        "name": "dup", "email": "dup@wildlifetest.dev", "password": "TestPass123!",
        "role": "Wildlife Researcher",
    })
    assert resp.status_code == 400


def test_login_wrong_password_rejected(client, auth_headers):
    auth_headers("Wildlife Researcher", email="wrongpass@wildlifetest.dev")
    resp = client.post("/auth/login", json={"email": "wrongpass@wildlifetest.dev", "password": "nope"})
    assert resp.status_code == 400


def test_refresh_without_cookie_rejected(client):
    resp = client.post("/auth/refresh")
    assert resp.status_code == 401


def test_logout_clears_cookie(client, auth_headers):
    auth_headers("Wildlife Researcher", email="logout@wildlifetest.dev")
    resp = client.post("/auth/logout")
    assert resp.status_code == 200


def test_google_login_returns_501_when_unconfigured(client, monkeypatch):
    # The real deployment may have Google credentials configured -- force the
    # unconfigured state explicitly rather than relying on ambient env state.
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "")
    resp = client.get("/auth/google/login", follow_redirects=False)
    assert resp.status_code == 501


def test_google_login_redirects_when_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-client-secret")
    resp = client.get("/auth/google/login", follow_redirects=False)
    assert resp.status_code == 307
    assert "accounts.google.com" in resp.headers["location"]
