"""
Unit tests for src/agent/pre_analyzer.py

Tests every rule in isolation and combined, plus edge cases.
All tests are pure Python — no DB, no network, no LLM.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from statistics import median

import pytest

from src.agent.pre_analyzer import (
    analyze_transactions,
    build_findings_context,
    HIGH_RISK_COUNTRIES,
    STRUCTURING_LOW,
    STRUCTURING_HIGH,
    VELOCITY_THRESHOLD,
    LARGE_AMOUNT_MULTIPLIER,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _tx(tx_id, amount, country_code="US", created_at=None):
    if created_at is None:
        created_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return {
        "id": tx_id,
        "amount": amount,
        "country_code": country_code,
        "created_at": created_at.isoformat(),
        "category": "wire_transfer",
    }


# ── Empty / trivial input ──────────────────────────────────────────────────────

def test_empty_input_returns_no_findings():
    assert analyze_transactions([]) == []


def test_single_normal_transaction_no_findings():
    txns = [_tx("id-001", 500.00)]
    assert analyze_transactions(txns) == []


def test_missing_id_skipped():
    """Transactions without an id field must not crash and are ignored."""
    txns = [{"amount": 9500.00, "country_code": "US",
              "created_at": "2026-01-01T12:00:00+00:00"}]
    findings = analyze_transactions(txns)
    assert findings == []


# ── Structuring rule ───────────────────────────────────────────────────────────

def test_structuring_exactly_at_lower_bound():
    txns = [_tx("id-001", float(STRUCTURING_LOW))]
    findings = analyze_transactions(txns)
    assert len(findings) == 1
    assert findings[0]["anomaly_type"] == "structuring"
    assert findings[0]["severity"] == "high"
    assert findings[0]["transaction_id"] == "id-001"


def test_structuring_exactly_at_upper_bound():
    txns = [_tx("id-001", float(STRUCTURING_HIGH))]
    findings = analyze_transactions(txns)
    assert len(findings) == 1
    assert findings[0]["anomaly_type"] == "structuring"


def test_structuring_just_below_lower_bound_not_flagged():
    txns = [_tx("id-001", float(STRUCTURING_LOW) - 0.01)]
    assert analyze_transactions(txns) == []


def test_structuring_just_above_upper_bound_not_flagged():
    txns = [_tx("id-001", float(STRUCTURING_HIGH) + 0.01)]
    # Could trigger large-amount if median is low — use same amount for all
    txns = [_tx(f"id-{i:03d}", float(STRUCTURING_HIGH) + 1.0) for i in range(3)]
    for f in analyze_transactions(txns):
        assert f["anomaly_type"] != "structuring"


def test_structuring_multiple_transactions():
    txns = [
        _tx("id-001", 9_000.00),
        _tx("id-002", 9_500.00),
        _tx("id-003", 200.00),   # normal
    ]
    findings = analyze_transactions(txns)
    structuring = [f for f in findings if f["anomaly_type"] == "structuring"]
    assert len(structuring) == 2
    ids = {f["transaction_id"] for f in structuring}
    assert ids == {"id-001", "id-002"}


def test_structuring_evidence_mentions_amount():
    txns = [_tx("id-001", 9_500.00)]
    findings = analyze_transactions(txns)
    assert "9,500.00" in findings[0]["evidence"]
    assert "10,000" in findings[0]["evidence"]


# ── Geographic rule ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("country_code", sorted(HIGH_RISK_COUNTRIES))
def test_all_high_risk_countries_flagged(country_code):
    txns = [_tx("id-001", 1_000.00, country_code=country_code)]
    findings = analyze_transactions(txns)
    assert any(f["anomaly_type"] == "geographic" for f in findings)


def test_low_risk_country_not_flagged():
    for cc in ("US", "GB", "DE", "CA", "FR", "AU", "JP"):
        txns = [_tx("id-001", 1_000.00, country_code=cc)]
        geo = [f for f in analyze_transactions(txns) if f["anomaly_type"] == "geographic"]
        assert geo == [], f"Expected no geo finding for {cc}"


def test_geographic_finding_has_correct_id():
    txns = [_tx("geo-txn-abc", 500.00, country_code="IR")]
    findings = analyze_transactions(txns)
    geo = [f for f in findings if f["anomaly_type"] == "geographic"]
    assert len(geo) == 1
    assert geo[0]["transaction_id"] == "geo-txn-abc"


def test_geographic_country_code_case_insensitive():
    """Lower-case country codes should also be caught."""
    txns = [_tx("id-001", 500.00, country_code="ng")]
    findings = analyze_transactions(txns)
    geo = [f for f in findings if f["anomaly_type"] == "geographic"]
    assert len(geo) == 1


# ── Large amount rule ──────────────────────────────────────────────────────────

def test_large_amount_above_threshold():
    # amounts: [100, 100, 100] → median = 100 → 3× = 300 → 1000 triggers it
    txns = [
        _tx("id-001", 100.00),
        _tx("id-002", 100.00),
        _tx("id-003", 1_000.00),   # 10× median
    ]
    findings = analyze_transactions(txns)
    large = [f for f in findings if f["anomaly_type"] == "amount"]
    assert len(large) == 1
    assert large[0]["transaction_id"] == "id-003"


def test_large_amount_exactly_at_threshold_not_flagged():
    # 3.0× median is NOT > 3×, so should not trigger
    txns = [
        _tx("id-001", 100.00),
        _tx("id-002", 100.00),
        _tx("id-003", 300.00),   # exactly 3× median of 100
    ]
    findings = analyze_transactions(txns)
    large = [f for f in findings if f["anomaly_type"] == "amount"]
    assert large == []


def test_large_amount_evidence_shows_multiple():
    txns = [
        _tx("id-001", 50.00),
        _tx("id-002", 50.00),
        _tx("id-003", 500.00),   # 10× median
    ]
    findings = analyze_transactions(txns)
    large = [f for f in findings if f["anomaly_type"] == "amount"]
    assert len(large) == 1
    assert "×" in large[0]["evidence"]


# ── Velocity rule ──────────────────────────────────────────────────────────────

def test_velocity_above_threshold():
    base = datetime(2026, 3, 19, 0, 0, 0, tzinfo=timezone.utc)
    txns = [
        _tx(f"vel-{i:03d}", 100.00, created_at=base + timedelta(hours=i))
        for i in range(VELOCITY_THRESHOLD + 1)   # one more than threshold
    ]
    findings = analyze_transactions(txns)
    vel = [f for f in findings if f["anomaly_type"] == "velocity"]
    assert len(vel) >= 1


def test_velocity_exactly_at_threshold_not_flagged():
    base = datetime(2026, 3, 19, 0, 0, 0, tzinfo=timezone.utc)
    txns = [
        _tx(f"vel-{i:03d}", 100.00, created_at=base + timedelta(hours=i))
        for i in range(VELOCITY_THRESHOLD)   # exactly at threshold, not above
    ]
    findings = analyze_transactions(txns)
    vel = [f for f in findings if f["anomaly_type"] == "velocity"]
    assert vel == []


def test_velocity_spread_over_multiple_days_not_flagged():
    base = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
    txns = [
        _tx(f"vel-{i:03d}", 100.00, created_at=base + timedelta(days=i))
        for i in range(VELOCITY_THRESHOLD + 1)
    ]
    findings = analyze_transactions(txns)
    vel = [f for f in findings if f["anomaly_type"] == "velocity"]
    assert vel == []


def test_velocity_without_timestamps_not_flagged():
    """Transactions missing created_at are excluded from velocity checks."""
    txns = [{"id": f"id-{i:03d}", "amount": 100.0} for i in range(10)]
    findings = analyze_transactions(txns)
    vel = [f for f in findings if f["anomaly_type"] == "velocity"]
    assert vel == []


# ── Deduplication (seen_ids) ───────────────────────────────────────────────────

def test_transaction_flagged_only_once_when_multiple_rules_match():
    """A structuring transaction to a high-risk country should appear once."""
    txns = [_tx("id-001", 9_500.00, country_code="NG")]
    findings = analyze_transactions(txns)
    ids = [f["transaction_id"] for f in findings]
    assert ids.count("id-001") == 1


# ── build_findings_context ─────────────────────────────────────────────────────

def test_build_findings_context_no_findings():
    ctx = build_findings_context("acct-123", [], [])
    assert "No anomalies detected" in ctx


def test_build_findings_context_with_findings():
    findings = [
        {
            "transaction_id": "real-uuid-001",
            "anomaly_type": "structuring",
            "severity": "high",
            "evidence": "Amount in structuring range",
            "policy_reference": "AML Policy",
        }
    ]
    ctx = build_findings_context("acct-123", [], findings)
    assert "real-uuid-001" in ctx
    assert "structuring" in ctx
    assert "Copy transaction_ids EXACTLY" in ctx


def test_build_findings_context_includes_account_id():
    ctx = build_findings_context("acct-xyz-999", [], [])
    assert "acct-xyz-999" in ctx
