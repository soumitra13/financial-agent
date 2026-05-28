"""
rate_limiter.py — Per-task tool call caps.

Prevents the agent from hammering write tools in a runaway loop.
Limits are intentionally conservative for a compliance agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.guardrails.allowlist import GuardrailViolation


# ── Configurable limits ───────────────────────────────────────────────────────

LIMITS: dict[str, int] = {
    "flag_anomaly":               5,   # max flags per task
    "draft_customer_explanation": 1,   # only one draft per task
    "check_policy_compliance":    10,  # generous but bounded
    "search_similar_transactions": 5,
    "get_account_transactions":   5,
    "get_account_profile":        3,
}

DEFAULT_LIMIT = 20   # fallback for any tool not explicitly listed


@dataclass
class RateLimiter:
    """
    Tracks call counts per tool for a single task run.
    Call .check() before execution, .record() after.
    """
    _counts: dict[str, int] = field(default_factory=dict)

    def check(self, tool_name: str) -> None:
        """Raise GuardrailViolation if the tool has hit its limit."""
        limit = LIMITS.get(tool_name, DEFAULT_LIMIT)
        current = self._counts.get(tool_name, 0)
        if current >= limit:
            raise GuardrailViolation(
                tool_name,
                f"rate limit exceeded: called {current}/{limit} times this task",
            )

    def record(self, tool_name: str) -> None:
        """Increment the counter for a tool after it executes."""
        self._counts[tool_name] = self._counts.get(tool_name, 0) + 1

    def counts(self) -> dict[str, int]:
        """Return a snapshot of current call counts (for audit logging)."""
        return dict(self._counts)

    def remaining(self, tool_name: str) -> int:
        """How many more calls are allowed for this tool."""
        limit = LIMITS.get(tool_name, DEFAULT_LIMIT)
        return max(0, limit - self._counts.get(tool_name, 0))
