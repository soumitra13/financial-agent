"""
Unit tests for all four guardrail modules.
No DB, no network — pure in-process logic.
"""

from __future__ import annotations

import pytest

# ══════════════════════════════════════════════════════════════════════════════
# Allowlist (read-before-write ordering)
# ══════════════════════════════════════════════════════════════════════════════

class TestAllowlist:
    def setup_method(self):
        from src.guardrails.allowlist import GuardrailContext
        self.ctx = GuardrailContext()

    def test_read_tool_allowed_first(self):
        """get_account_transactions is a read — should always be allowed."""
        self.ctx.check("get_account_transactions")   # must not raise

    def test_write_blocked_before_required_read(self):
        """flag_anomaly requires get_account_transactions first."""
        from src.guardrails.allowlist import GuardrailViolation
        with pytest.raises(GuardrailViolation, match="prerequisite"):
            self.ctx.check("flag_anomaly")

    def test_write_allowed_after_prerequisite(self):
        """flag_anomaly is allowed after get_account_transactions is recorded."""
        self.ctx.check("get_account_transactions")
        self.ctx.record("get_account_transactions")
        self.ctx.check("flag_anomaly")   # must not raise

    def test_call_history_recorded(self):
        self.ctx.check("get_account_transactions")
        self.ctx.record("get_account_transactions")
        assert "get_account_transactions" in self.ctx.call_history

    def test_unknown_tool_allowed(self):
        """Tools not in the prerequisites dict should pass through."""
        self.ctx.check("check_policy_compliance")   # not in prerequisites → OK


# ══════════════════════════════════════════════════════════════════════════════
# Rate limiter
# ══════════════════════════════════════════════════════════════════════════════

class TestRateLimiter:
    def setup_method(self):
        from src.guardrails.rate_limiter import RateLimiter
        self.rl = RateLimiter()

    def test_within_limit_allowed(self):
        # flag_anomaly limit = 5; first 5 calls should pass
        for _ in range(5):
            self.rl.check("flag_anomaly")
            self.rl.record("flag_anomaly")

    def test_exceeding_limit_blocked(self):
        from src.guardrails.allowlist import GuardrailViolation
        for _ in range(5):
            self.rl.check("flag_anomaly")
            self.rl.record("flag_anomaly")
        with pytest.raises(GuardrailViolation, match="limit"):
            self.rl.check("flag_anomaly")

    def test_get_account_transactions_capped_at_five(self):
        """get_account_transactions has a limit of 5 (prevents runaway fetching)."""
        from src.guardrails.allowlist import GuardrailViolation
        for _ in range(5):
            self.rl.check("get_account_transactions")
            self.rl.record("get_account_transactions")
        with pytest.raises(GuardrailViolation, match="limit"):
            self.rl.check("get_account_transactions")

    def test_unknown_tool_uses_default_limit(self):
        """Tools not in LIMITS fall back to DEFAULT_LIMIT=20."""
        from src.guardrails.rate_limiter import DEFAULT_LIMIT
        for _ in range(DEFAULT_LIMIT):
            self.rl.check("some_unknown_tool")
            self.rl.record("some_unknown_tool")
        from src.guardrails.allowlist import GuardrailViolation
        with pytest.raises(GuardrailViolation):
            self.rl.check("some_unknown_tool")

    def test_counts_tracks_calls(self):
        self.rl.check("get_account_transactions")
        self.rl.record("get_account_transactions")
        self.rl.check("get_account_transactions")
        self.rl.record("get_account_transactions")
        counts = self.rl.counts()
        assert counts.get("get_account_transactions", 0) == 2

    def test_draft_customer_explanation_capped_at_one(self):
        from src.guardrails.allowlist import GuardrailViolation
        self.rl.check("draft_customer_explanation")
        self.rl.record("draft_customer_explanation")
        with pytest.raises(GuardrailViolation):
            self.rl.check("draft_customer_explanation")


# ══════════════════════════════════════════════════════════════════════════════
# PII scrubber
# ══════════════════════════════════════════════════════════════════════════════

class TestPIIScrubber:
    """
    scrub_tool_result skips strings < 50 chars (pure IDs).
    All test payloads are padded to exceed that threshold.
    """

    def _scrub(self, text):
        from src.guardrails.pii_scrubber import scrub_tool_result
        result, redactions = scrub_tool_result(text)
        return result, redactions

    def _pad(self, text: str) -> str:
        """Ensure the string is at least 50 chars so the early-exit doesn't fire."""
        return text + ("_" * max(0, 50 - len(text) + 1))

    def test_ssn_redacted(self):
        text = self._pad('{"account": "acct-001", "note": "SSN is 123-45-6789"}')
        result, redactions = self._scrub(text)
        assert "123-45-6789" not in result
        assert any("ssn" in r.lower() for r in redactions)

    def test_credit_card_redacted(self):
        text = self._pad('{"account": "acct-001", "card": "4111-1111-1111-1111"}')
        result, redactions = self._scrub(text)
        assert "4111-1111-1111-1111" not in result
        assert any("card" in r.lower() for r in redactions)

    def test_phone_number_redacted(self):
        text = self._pad('{"account": "acct-001", "phone": "555-867-5309"}')
        result, redactions = self._scrub(text)
        assert "555-867-5309" not in result
        assert any("phone" in r.lower() for r in redactions)

    def test_email_redacted(self):
        text = self._pad('{"account": "acct-001", "email": "john.doe@example.com"}')
        result, redactions = self._scrub(text)
        assert "john.doe@example.com" not in result
        assert any("email" in r.lower() for r in redactions)

    def test_email_domain_preserved_in_masked_value(self):
        """Email masking keeps the domain for context — only local part is hidden."""
        text = self._pad('{"account": "acct-001", "email": "john.doe@example.com"}')
        result, _ = self._scrub(text)
        assert "example.com" in result

    def test_clean_text_unchanged(self):
        text = self._pad('{"amount": 9500.00, "country_code": "US", "id": "abc-123"}')
        result, redactions = self._scrub(text)
        assert result == text
        assert redactions == []

    def test_multiple_pii_types_in_one_string(self):
        # Note: SSNs starting with 9 are ITINs — excluded by the regex by design.
        # Use a standard SSN prefix (234-xx-xxxx) for this test.
        text = '{"account": "acct-001", "ssn": "234-56-7890", "email": "user@bank.com", "note": "flagged"}'
        result, redactions = self._scrub(text)
        assert "234-56-7890" not in result
        assert "user@bank.com" not in result
        assert len(redactions) >= 2

    def test_short_string_skipped(self):
        """Strings under 50 chars are returned unchanged — they're pure IDs."""
        text = '{"id": "abc"}'   # 13 chars — below threshold
        result, redactions = self._scrub(text)
        assert result == text
        assert redactions == []


# ══════════════════════════════════════════════════════════════════════════════
# Output validator
# ══════════════════════════════════════════════════════════════════════════════

class TestOutputValidator:
    def _validate(self, raw):
        from src.guardrails.output_validator import validate_output
        return validate_output(raw)

    def test_valid_output_passes(self):
        raw = {
            "summary": "Account shows structuring patterns.",
            "anomalies_found": [
                {
                    "transaction_id": "abc-123",
                    "anomaly_type": "structuring",
                    "severity": "high",
                    "evidence": "Amount in $8k-$10k range.",
                    "policy_reference": "AML Policy",
                }
            ],
            "policies_checked": ["AML Thresholds"],
            "recommendation": "Escalate for review.",
            "requires_escalation": False,
        }
        result = self._validate(raw)
        assert len(result.anomalies_found) == 1
        assert result.anomalies_found[0].transaction_id == "abc-123"

    def test_missing_summary_falls_back_to_recommendation(self):
        raw = {
            "recommendation": "Review this account.",
            "anomalies_found": [],
        }
        result = self._validate(raw)
        assert result.summary  # should not be empty

    def test_critical_anomaly_auto_sets_escalation(self):
        raw = {
            "summary": "Critical anomaly found.",
            "anomalies_found": [
                {
                    "transaction_id": "abc-001",
                    "anomaly_type": "structuring",
                    "severity": "critical",
                    "evidence": "Very suspicious.",
                }
            ],
            "recommendation": "Escalate immediately.",
        }
        result = self._validate(raw)
        assert result.requires_escalation is True
        assert result.escalation_reason is not None

    def test_high_severity_does_not_auto_escalate(self):
        """Only 'critical' triggers auto-escalation; 'high' does not."""
        raw = {
            "summary": "High severity anomaly.",
            "anomalies_found": [
                {
                    "transaction_id": "abc-002",
                    "anomaly_type": "geographic",
                    "severity": "high",
                    "evidence": "Transfer to high-risk country.",
                }
            ],
            "recommendation": "Monitor closely.",
        }
        result = self._validate(raw)
        assert result.requires_escalation is False

    def test_empty_anomalies_list_valid(self):
        raw = {
            "summary": "Account activity appears normal.",
            "anomalies_found": [],
            "recommendation": "No action required.",
        }
        result = self._validate(raw)
        assert result.anomalies_found == []
        assert result.requires_escalation is False

    def test_plain_text_input_returns_minimal_output(self):
        """When the LLM returns plain text instead of JSON."""
        result = self._validate("The account looks suspicious.")
        assert result.summary
        assert result.anomalies_found == []

    def test_invalid_severity_raises(self):
        from pydantic import ValidationError
        raw = {
            "summary": "Something found.",
            "anomalies_found": [
                {
                    "transaction_id": "abc-003",
                    "anomaly_type": "structuring",
                    "severity": "EXTREME",   # not in enum
                    "evidence": "Bad.",
                }
            ],
        }
        with pytest.raises((ValidationError, Exception)):
            self._validate(raw)

    def test_to_dict_returns_serializable_output(self):
        raw = {
            "summary": "All clear.",
            "anomalies_found": [],
            "recommendation": "Continue monitoring.",
        }
        result = self._validate(raw)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "anomalies_found" in d
        assert "summary" in d
