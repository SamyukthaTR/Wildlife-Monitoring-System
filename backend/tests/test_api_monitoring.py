"""Integration tests for site/survey/device management and role enforcement.
Needs a live database -- see conftest.py. Run with `pytest -m integration`.
"""

import pytest

pytestmark = pytest.mark.integration


def _create_site(client, headers, name="Test Reserve"):
    return client.post("/monitoring/sites", json={
        "location_name": name, "latitude": 1.5, "longitude": 36.8,
        "habitat_type": "savanna", "protected_area": "Test Park",
        "monitoring_device_type": "camera_trap",
    }, headers=headers)


def test_researcher_can_create_site(client, auth_headers):
    headers = auth_headers("Wildlife Researcher")
    resp = _create_site(client, headers)
    assert resp.status_code == 201
    assert resp.json()["latitude"] == 1.5


def test_forest_officer_cannot_create_site(client, auth_headers):
    headers = auth_headers("Forest Department Officer")
    resp = _create_site(client, headers)
    assert resp.status_code == 403


def test_create_survey_for_missing_site_returns_404(client, auth_headers):
    headers = auth_headers("Wildlife Researcher")
    resp = client.post("/monitoring/surveys", json={
        "site_id": 999999, "survey_date": "2026-01-01", "notes": "test",
    }, headers=headers)
    assert resp.status_code == 404


def test_duplicate_device_serial_rejected(client, auth_headers):
    headers = auth_headers("Wildlife Researcher")
    site = _create_site(client, headers).json()
    device_payload = {
        "site_id": site["id"], "device_type": "camera_trap", "serial": "CT-0001", "status": "active",
    }
    first = client.post("/monitoring/devices", json=device_payload, headers=headers)
    assert first.status_code == 201
    second = client.post("/monitoring/devices", json=device_payload, headers=headers)
    assert second.status_code == 400


def test_list_sites_requires_authentication(client):
    resp = client.get("/monitoring/sites")
    assert resp.status_code == 401
