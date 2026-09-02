"""Integration tests for admin-only user management and platform overview.
Needs a live database -- see conftest.py. Run with `pytest -m integration`.
"""

import pytest

pytestmark = pytest.mark.integration


def test_non_admin_forbidden_from_overview(client, auth_headers):
    headers = auth_headers("Wildlife Researcher")
    assert client.get("/admin/overview", headers=headers).status_code == 403
    assert client.get("/users", headers=headers).status_code == 403


def test_admin_overview_shape(client, auth_headers):
    headers = auth_headers("Administrator")
    resp = client.get("/admin/overview", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "users" in body and "monitoring" in body and "observations" in body
    assert "analysis" in body and "species" in body
    assert body["users"]["total"] >= 1


def test_admin_can_list_and_update_role(client, auth_headers):
    admin_headers = auth_headers("Administrator")
    researcher_headers = auth_headers("Wildlife Researcher", email="target@wildlifetest.dev")

    listing = client.get("/users", headers=admin_headers)
    assert listing.status_code == 200
    target = next(u for u in listing.json() if u["email"] == "target@wildlifetest.dev")

    updated = client.patch(
        f"/users/{target['id']}/role", json={"role": "Conservation Officer"}, headers=admin_headers
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "Conservation Officer"


def test_admin_cannot_delete_self(client, auth_headers):
    admin_headers = auth_headers("Administrator")
    me = client.get("/users/me", headers=admin_headers).json()
    resp = client.delete(f"/users/{me['id']}", headers=admin_headers)
    assert resp.status_code == 400


def test_admin_can_delete_other_user(client, auth_headers):
    admin_headers = auth_headers("Administrator")
    researcher_headers = auth_headers("Wildlife Researcher", email="removable@wildlifetest.dev")
    target = client.get("/users/me", headers=researcher_headers).json()

    resp = client.delete(f"/users/{target['id']}", headers=admin_headers)
    assert resp.status_code == 204
