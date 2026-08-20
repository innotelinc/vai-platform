"""Tests for the Grist-backed interview results route."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.constants import GRIST_API_KEY, GRIST_BASE_URL, GRIST_DOC_ID
from api.routes.interviews import router
from api.services.auth.depends import get_user

# Patch the module-level constants so the route uses test values.
ROUTE_MODULE = "api.routes.interviews"


@pytest.fixture(autouse=True)
def _grist_env(monkeypatch):
    monkeypatch.setattr(f"{ROUTE_MODULE}.GRIST_BASE_URL", "http://grist-test:8484")
    monkeypatch.setattr(f"{ROUTE_MODULE}.GRIST_DOC_ID", "doc-test")
    monkeypatch.setattr(f"{ROUTE_MODULE}.GRIST_API_KEY", "key-test")


def _make_test_app() -> FastAPI:
    app = FastAPI()

    async def _fake_get_user():
        return object()

    app.dependency_overrides[get_user] = _fake_get_user
    app.include_router(router)
    return app


def _records_payload():
    return {
        "records": [
            {
                "id": 2,
                "fields": {
                    "Student": "Jordan Avery",
                    "Phone": "+15550000000",
                    "RunID": "3",
                    "Score": 4,
                    "Verdict": "review",
                    "Dimensions": '{"triage": {"score": 3, "evidence": "asked twice"}}',
                    "Strengths": '["clear greeting"]',
                    "Improvements": '["confirm resolution"]',
                    "Transcript": "Hello, this is Jordan.",
                },
            },
            {
                "id": 1,
                "fields": {
                    "Student": "Sam Lee",
                    "Phone": "+15550000001",
                    "RunID": "2",
                    "Score": 8,
                    "Verdict": "pass",
                    "Dimensions": "not-json",
                    "Strengths": None,
                    "Improvements": None,
                    "Transcript": "Good morning.",
                },
            },
        ]
    }


def test_list_interviews_returns_newest_first_and_summary():
    app = _make_test_app()

    async def _fake_get(url, headers=None):
        assert url == f"{GRIST_BASE_URL}/api/docs/{GRIST_DOC_ID}/tables/Interviews/records"
        assert headers == {"Authorization": "Bearer key-test"}
        return httpx.Response(200, json=_records_payload())

    with patch(f"{ROUTE_MODULE}.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = _fake_get
        client = TestClient(app)
        resp = client.get("/api/v1/interviews")

    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    # Newest first (id desc).
    assert [i["id"] for i in data["interviews"]] == [2, 1]
    assert data["interviews"][0]["student"] == "Jordan Avery"
    assert data["interviews"][0]["dimensions"]["triage"]["score"] == 3
    assert data["interviews"][0]["strengths"] == ["clear greeting"]
    # Invalid JSON stays None rather than crashing.
    assert data["interviews"][1]["dimensions"] is None

    summary = data["summary"]
    assert summary["total"] == 2
    assert summary["pass_count"] == 1
    assert summary["review_count"] == 1
    assert summary["fail_count"] == 0
    assert summary["average_score"] == 6.0


def test_list_interviews_when_grist_unconfigured():
    with patch(f"{ROUTE_MODULE}.GRIST_DOC_ID", ""):
        app = _make_test_app()
        client = TestClient(app)
        resp = client.get("/api/v1/interviews")

    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is False
    assert data["interviews"] == []
    assert data["summary"]["total"] == 0


def test_list_interviews_propagates_grist_errors():
    app = _make_test_app()

    async def _fake_get(url, headers=None):
        raise httpx.HTTPStatusError(
            "401 Unauthorized",
            request=httpx.Request("GET", url),
            response=httpx.Response(401, request=httpx.Request("GET", url)),
        )

    with patch(f"{ROUTE_MODULE}.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = _fake_get
        client = TestClient(app)
        resp = client.get("/api/v1/interviews")

    assert resp.status_code == 500


def test_list_interviews_requires_auth():
    app = _make_test_app()

    async def _fake_get_user():
        raise PermissionError

    app.dependency_overrides[get_user] = _fake_get_user
    client = TestClient(app)
    with pytest.raises(PermissionError):
        client.get("/api/v1/interviews")
