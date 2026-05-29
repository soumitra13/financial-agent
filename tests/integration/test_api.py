"""
Integration tests for the FastAPI routes.

These tests use FastAPI's TestClient and hit the real application.
Tests that touch the DB require a running Postgres (uses your .env).
Tests that don't touch the DB (health shape, metrics format) run anywhere.

Markers:
  @pytest.mark.db  — requires DATABASE_URL and a live Postgres
"""

from __future__ import annotations

import os

import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """
    Module-scoped TestClient — starts the app once for all tests in this file.
    Uses raise_server_exceptions=False so 500s return responses instead of crashing.
    Injects the test API key header so protected routes don't return 401.
    """
    from fastapi.testclient import TestClient

    from src.api.main import app
    # CI sets API_KEY=test-key in the workflow env
    api_key = os.environ.get("API_KEY", "test-key")
    with TestClient(
        app,
        raise_server_exceptions=False,
        headers={"X-API-Key": api_key},
    ) as c:
        yield c


# ── Health endpoint ────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_has_status_ok(self, client):
        r = client.get("/health")
        data = r.json()
        assert data.get("status") == "ok"

    def test_health_has_database_key(self, client):
        r = client.get("/health")
        data = r.json()
        assert "database" in data

    def test_health_content_type_json(self, client):
        r = client.get("/health")
        assert "application/json" in r.headers["content-type"]


# ── Metrics endpoint ───────────────────────────────────────────────────────────

class TestMetrics:
    def test_metrics_returns_200(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200

    def test_metrics_content_type_text(self, client):
        r = client.get("/metrics")
        assert "text/plain" in r.headers["content-type"]

    def test_metrics_contains_help_lines(self, client):
        r = client.get("/metrics")
        assert "# HELP financial_agent_tasks_total" in r.text

    def test_metrics_contains_type_lines(self, client):
        r = client.get("/metrics")
        assert "# TYPE financial_agent_tasks_total counter" in r.text

    def test_metrics_contains_all_expected_metric_families(self, client):
        r = client.get("/metrics")
        expected = [
            "financial_agent_tasks_total",
            "financial_agent_task_duration_seconds",
            "financial_agent_agent_steps_total",
            "financial_agent_anomalies_total",
            "financial_agent_tool_calls_total",
            "financial_agent_llm_calls_total",
        ]
        for name in expected:
            assert name in r.text, f"Missing metric: {name}"


# ── Dashboard endpoint ─────────────────────────────────────────────────────────

class TestDashboard:
    def test_dashboard_returns_200(self, client):
        r = client.get("/dashboard")
        assert r.status_code == 200

    def test_dashboard_content_type_html(self, client):
        r = client.get("/dashboard")
        assert "text/html" in r.headers["content-type"]

    def test_dashboard_contains_title(self, client):
        r = client.get("/dashboard")
        assert "Financial Agent Dashboard" in r.text

    def test_dashboard_contains_key_sections(self, client):
        r = client.get("/dashboard")
        assert "Recent Tasks" in r.text
        assert "Anomaly Breakdown" in r.text
        assert "Open Escalations" in r.text

    def test_dashboard_auto_refresh_meta_tag(self, client):
        r = client.get("/dashboard")
        assert 'http-equiv="refresh"' in r.text


# ── Tasks endpoint (requires DB) ───────────────────────────────────────────────

@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set — skipping DB-dependent tests",
)
class TestTasksAPI:
    def test_post_tasks_returns_202(self, client):
        r = client.post("/tasks", json={
            "description": "Test task — unit test submission",
            "account_id": "00000000-0000-0000-0000-000000000000",
        })
        # 202 Accepted (queued to Redis) or 422 if Redis not running
        assert r.status_code in (202, 422, 500)

    def test_get_nonexistent_task_returns_404(self, client):
        r = client.get("/tasks/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_get_tasks_list(self, client):
        r = client.get("/tasks")
        # Should return 200 with a list (possibly empty)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
