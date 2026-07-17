"""API contract tests for the /api/cases router."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

KEY = {"X-API-Key": settings.edge_api_key}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_list_cases(client):
    r = client.get("/api/cases", headers=KEY)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 15
    assert len(body["cases"]) == 15


def test_requires_api_key(client):
    assert client.get("/api/cases").status_code == 401


def test_get_single_case(client):
    r = client.get("/api/cases/13", headers=KEY)
    assert r.status_code == 200
    assert r.json()["slug"] == "ppe-compliance"


def test_unknown_case_404(client):
    assert client.get("/api/cases/99", headers=KEY).status_code == 404
    assert client.get("/api/cases/99/demo", headers=KEY).status_code == 404


@pytest.mark.parametrize("case_id", list(range(1, 16)))
def test_demo_endpoint(client, case_id):
    r = client.get(f"/api/cases/{case_id}/demo", headers=KEY)
    assert r.status_code == 200
    assert r.json()["result"]["status"] in {"normal", "warning", "critical"}


def test_run_endpoint_with_payload(client):
    payload = {"persons": [{"id": "T1", "ppe": ["vest"], "in_restricted_zone": False}]}
    r = client.post("/api/cases/13/run", headers=KEY, json={"payload": payload})
    assert r.status_code == 200
    assert r.json()["metrics"]["person_count"] == 1


def test_run_endpoint_bad_payload_422(client):
    r = client.post("/api/cases/5/run", headers=KEY, json={"payload": {}})
    assert r.status_code == 422


def test_descriptors_include_briefs_and_architecture(client):
    cases = client.get("/api/cases", headers=KEY).json()["cases"]
    for c in cases:
        assert c["architecture_type"], c["case_id"]
        assert c["why_distinct"], c["case_id"]
        assert c["brief"]["problem"], c["case_id"]
        assert c["brief"]["solution"], c["case_id"]


@pytest.mark.parametrize("case_id", [1, 5, 8, 13])
def test_source_endpoint_returns_real_code(client, case_id):
    r = client.get(f"/api/cases/{case_id}/source", headers=KEY)
    assert r.status_code == 200
    body = r.json()
    assert body["filename"].startswith(f"case{case_id:02d}_")
    assert "class" in body["source"] and "def compute" in body["source"]
    assert body["lines"] > 50


def test_source_endpoint_unknown_case_404(client):
    assert client.get("/api/cases/99/source", headers=KEY).status_code == 404
