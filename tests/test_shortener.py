from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

TEST_API_KEY = "test-api-key"


def _build_client(
    tmp_path: Path,
    *,
    api_rate_limit: int = 120,
    redirect_rate_limit: int = 240,
) -> TestClient:
    db_path = tmp_path / "test.db"
    os.environ["SHORTENER_DB_PATH"] = str(db_path)
    os.environ["SHORTENER_BASE_URL"] = "http://testserver"
    os.environ["SHORTENER_API_KEY"] = TEST_API_KEY
    os.environ["SHORTENER_API_RATE_LIMIT_PER_MINUTE"] = str(api_rate_limit)
    os.environ["SHORTENER_REDIRECT_RATE_LIMIT_PER_MINUTE"] = str(redirect_rate_limit)
    import importlib

    import app.main

    importlib.reload(app.main)
    return TestClient(app.main.app)


def _auth_headers() -> dict[str, str]:
    return {"X-API-Key": TEST_API_KEY}


def test_create_and_resolve_short_url(tmp_path: Path) -> None:
    client = _build_client(tmp_path)

    create_response = client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/docs", "ttl_days": 30},
        headers=_auth_headers(),
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    short_code = payload["short_code"]
    assert payload["short_url"].endswith(short_code)

    redirect_response = client.get(
        f"/{short_code}",
        headers={"user-agent": "pytest-agent"},
        follow_redirects=False,
    )
    assert redirect_response.status_code == 307
    assert redirect_response.headers["location"] == "https://example.com/docs"


def test_custom_alias_conflict_returns_409(tmp_path: Path) -> None:
    client = _build_client(tmp_path)

    first = client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/a", "custom_alias": "myalias"},
        headers=_auth_headers(),
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/b", "custom_alias": "myalias"},
        headers=_auth_headers(),
    )
    assert second.status_code == 409


def test_analytics_counts_clicks_and_unique_visitors(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    created = client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/metrics"},
        headers=_auth_headers(),
    ).json()
    code = created["short_code"]

    client.get(f"/{code}", headers={"user-agent": "ua-1"}, follow_redirects=False)
    client.get(f"/{code}", headers={"user-agent": "ua-1"}, follow_redirects=False)
    client.get(f"/{code}", headers={"user-agent": "ua-2"}, follow_redirects=False)

    analytics = client.get(f"/api/v1/analytics/{code}", headers=_auth_headers())
    assert analytics.status_code == 200
    body = analytics.json()
    assert body["total_clicks"] == 3
    assert body["unique_visitors"] == 2
    assert body["last_accessed_at"] is not None


def test_interactive_ui_is_available(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    response = client.get("/ui")
    assert response.status_code == 200
    assert "Agentic URL Shortener" in response.text
    assert "<form id=\"create-form\">" in response.text


def test_interactive_ui_renders_analytics_as_an_accessible_table(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    response = client.get("/ui")

    assert response.status_code == 200
    assert '<div id="analytics-result"' in response.text
    assert "<caption>Link analytics</caption>" in response.text
    assert response.text.count('scope="row"') == 4
    for value_id in (
        "analytics-short-code",
        "analytics-total-clicks",
        "analytics-unique-visitors",
        "analytics-last-accessed-at",
    ):
        assert f'id="{value_id}"' in response.text

    assert "analyticsShortCode.textContent" in response.text
    assert "analyticsTotalClicks.textContent" in response.text
    assert "analyticsUniqueVisitors.textContent" in response.text
    assert "analyticsLastAccessedAt.textContent" in response.text
    assert 'data.last_accessed_at === null ? "Never"' in response.text
    assert "await fetchAnalytics(code);" in response.text
    assert "fetchAndRender(`/api/v1/analytics/${code}`)" not in response.text


def test_auth_is_required_for_api_calls(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    response = client.post("/api/v1/shorten", json={"url": "https://example.com/secure"})
    assert response.status_code == 401


def test_rate_limit_returns_429(tmp_path: Path) -> None:
    client = _build_client(tmp_path, api_rate_limit=1)
    first = client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/rate-1"},
        headers=_auth_headers(),
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/rate-2"},
        headers=_auth_headers(),
    )
    assert second.status_code == 429
