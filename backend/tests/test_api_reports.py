"""Integration tests for the report export endpoints (JSON/CSV/PDF/Excel).
Needs a live database -- see conftest.py. Run with `pytest -m integration`.
"""

import pytest

pytestmark = pytest.mark.integration

CONTENT_TYPES = {
    "json": "application/json",
    "csv": "text/csv",
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@pytest.mark.parametrize("format", ["json", "csv", "pdf", "xlsx"])
def test_monitoring_report_all_formats(client, auth_headers, format):
    headers = auth_headers("Wildlife Researcher")
    resp = client.get("/reports/monitoring", params={"format": format}, headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(CONTENT_TYPES[format])
    if format in ("pdf", "xlsx"):
        assert len(resp.content) > 100


@pytest.mark.parametrize("format", ["json", "csv", "pdf", "xlsx"])
def test_habitat_report_all_formats_no_site(client, auth_headers, format):
    headers = auth_headers("Wildlife Researcher")
    resp = client.get("/reports/habitat", params={"format": format}, headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(CONTENT_TYPES[format])


@pytest.mark.parametrize("format", ["json", "csv", "pdf", "xlsx"])
def test_conservation_report_all_formats_no_site(client, auth_headers, format):
    headers = auth_headers("Wildlife Researcher")
    resp = client.get("/reports/conservation", params={"format": format}, headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(CONTENT_TYPES[format])


def test_habitat_report_missing_site_404(client, auth_headers):
    headers = auth_headers("Wildlife Researcher")
    resp = client.get("/reports/habitat", params={"site_id": 999999}, headers=headers)
    assert resp.status_code == 404


def test_conservation_report_missing_site_404(client, auth_headers):
    headers = auth_headers("Wildlife Researcher")
    resp = client.get("/reports/conservation", params={"site_id": 999999}, headers=headers)
    assert resp.status_code == 404


def test_species_population_report_json(client, auth_headers):
    headers = auth_headers("Wildlife Researcher")
    resp = client.get("/reports/species-population", headers=headers)
    assert resp.status_code == 200
    assert "rows" in resp.json()
