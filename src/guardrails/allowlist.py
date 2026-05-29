"""
allowlist.py — Tool call ordering and allowlist guardrail.

Rules enforced per task run:
  1. Only registered tools may be called (hard block).
  2. flag_anomaly requires a prior get_account_transactions or get_account_profile call.
  3. draft_customer_explanation requires a prior flag_anomaly call.
  4. check_policy_compliance may always be called (read-only).

Usage:
    ctx = GuardrailContext()
    ctx.check("flag_anomaly")   # raises GuardrailViolation if precondition not met
    ctx.record("flag_anomaly")  # call after successful execution
"""

from __future__ import annotations

# Tools the agent is allowed to call at all
ALLOWED_TOOLS: frozenset[str] = frozenset({
    "get_account_transactions",
    "get_account_profile",
    "search_similar_transactions",
    "check_policy_compliance",
    "flag_anomaly",
    "draft_customer_explanation",
})

# write tools — counted by rate limiter and subject to ordering rules
WRITE_TOOLS: frozenset[str] = frozenset({
    "flag_anomaly",
    "draft_customer_explanation",
})

# Ordering prerequisites: tool → set of tools that must have been called first
PREREQUISITES: dict[str, frozenset[str]] = {
    "flag_anomaly": frozenset({
        "get_account_transactions",
        "get_account_profile",
    }),
    "draft_customer_explanation": frozenset({
        "flag_anomaly",
    }),
}


class GuardrailViolation(Exception):
    """Raised when a tool call violates a guardrail rule."""

    def __init__(self, tool: str, reason: str) -> None:
        self.tool = tool
        self.reason = reason
        super().__init__(f"[Guardrail] {tool}: {reason}")


class GuardrailContext:
    """
    Tracks tool call history for a single task run and enforces ordering rules.
    Instantiate once per task, pass into the agent loop.
    """

    def __init__(self) -> None:
        self._called: list[str] = []   # ordered history of tool names called

    # ── Public API ────────────────────────────────────────────────────────────

    def check(self, tool_name: str) -> None:
        """
        Validate that calling `tool_name` is permitted right now.
        Raises GuardrailViolation on any breach.
        """
        # 1. Allowlist check
        if tool_name not in ALLOWED_TOOLS:
            raise GuardrailViolation(
                tool_name,
                f"not in allowed tool list: {sorted(ALLOWED_TOOLS)}",
            )

        # 2. Prerequisite ordering check
        required = PREREQUISITES.get(tool_name)
        if required:
            called_set = set(self._called)
            if not required.intersection(called_set):
                raise GuardrailViolation(
                    tool_name,
                    f"prerequisite not met — must call one of {sorted(required)} first "
                    f"(called so far: {self._called or ['none']})",
                )

    def record(self, tool_name: str) -> None:
        """Record a successful tool call so subsequent checks can see it."""
        self._called.append(tool_name)

    # ── Introspection ─────────────────────────────────────────────────────────

    @property
    def call_history(self) -> list[str]:
        return list(self._called)

    def has_called(self, tool_name: str) -> bool:
        return tool_name in self._called

    def is_write_tool(self, tool_name: str) -> bool:
        return tool_name in WRITE_TOOLS
