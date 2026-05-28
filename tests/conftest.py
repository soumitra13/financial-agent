"""
conftest.py — Shared fixtures for the Financial Agent test suite.

Fixtures:
  sample_transactions  — list of dicts covering all four anomaly rules
  clean_transaction    — a single normal transaction
  api_client           — FastAPI TestClient (no real DB needed for unit tests)
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

import pytest


# ── Transaction fixtures ───────────────────────────────────────────────────────

def _tx(
    tx_id: str,
    amount: float,
    country_code: str = "US",
    created_at: datetime | None = None,
    category: str = "wire_transfer",
) -> dict[str, Any]:
    """Build a minimal transaction dict matching the DB schema."""
    if created_at is None:
        created_at = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    return {
        "id": tx_id,
        "amount": amount,
        "currency": "USD",
        "direction": "debit",
        "counterparty": "Test Corp",
        "category": category,
        "country_code": country_code,
        "is_flagged": False,
        "flag_reason": None,
        "created_at": created_at.isoformat(),
    }


@pytest.fixture
def clean_transaction() -> dict[str, Any]:
    """A perfectly normal transaction that should trigger no rules."""
    return _tx("clean-0001-0000-0000-000000000001", amount=500.00)


@pytest.fixture
def structuring_transactions() -> list[dict[str, Any]]:
    """Two transactions in the $8k–$9.9k structuring range."""
    return [
        _tx("struct-0001-0000-0000-000000000001", amount=9_500.00),
        _tx("struct-0002-0000-0000-000000000002", amount=8_200.00),
        _tx("normal-0001-0000-0000-000000000003", amount=300.00),
    ]


@pytest.fixture
def geo_risk_transactions() -> list[dict[str, Any]]:
    """One transfer to a high-risk jurisdiction (Nigeria)."""
    return [
        _tx("geo-0001-0000-0000-000000000001", amount=1_500.00, country_code="NG"),
        _tx("normal-0001-0000-0000-000000000002", amount=400.00, country_code="US"),
    ]


@pytest.fixture
def large_amount_transactions() -> list[dict[str, Any]]:
    """One transaction well above 3× the account median."""
    # median of [100, 150, 200] = 150 → 3× = 450 → 2000 triggers it
    return [
        _tx("large-0001-0000-0000-000000000001", amount=2_000.00),
        _tx("normal-0001-0000-0000-000000000002", amount=100.00),
        _tx("normal-0002-0000-0000-000000000003", amount=150.00),
        _tx("normal-0003-0000-0000-000000000004", amount=200.00),
    ]


@pytest.fixture
def velocity_transactions() -> list[dict[str, Any]]:
    """Six transactions within a 24-hour window (threshold is 5)."""
    base = datetime(2026, 3, 19, 0, 0, 0, tzinfo=timezone.utc)
    return [
        _tx(f"vel-000{i}-0000-0000-000000000{i:03d}",
            amount=100.00 + i,
            created_at=base + timedelta(hours=i))
        for i in range(1, 7)   # 6 transactions, all within 5 hours of each other
    ]


@pytest.fixture
def sample_transactions(
    structuring_transactions,
    geo_risk_transactions,
) -> list[dict[str, Any]]:
    """Combined set that exercises structuring and geo rules."""
    return structuring_transactions + geo_risk_transactions


# ── API test client ────────────────────────────────────────────────────────────

@pytest.fixture
def api_client():
    """
    FastAPI TestClient using the real app.
    Integration tests that hit DB endpoints will need a running Postgres.
    Unit-level API tests (health, metrics shape) work without it.
    """
    from fastapi.testclient import TestClient
    from src.api.main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
