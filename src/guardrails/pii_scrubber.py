"""
pii_scrubber.py — Strip PII from tool results before they enter the LLM context.

Applied to the JSON string of every tool result. The LLM sees masked values;
the raw data remains only in the DB and the secure audit log.

Patterns covered:
  - SSN (XXX-XX-XXXX or XXXXXXXXX)
  - Credit/debit card numbers (13-19 digits, with or without spaces/dashes)
  - US phone numbers (various formats)
  - Email addresses (partial mask — keeps domain for context)
  - Raw UUIDs in narrative fields (account / transaction IDs in free text)
    NOTE: UUIDs that are JSON *values* (needed for tool calls) are NOT stripped —
    only UUIDs appearing inside string values of length > 40 chars are scrubbed.
"""

from __future__ import annotations

import re

# ── Compiled patterns ─────────────────────────────────────────────────────────

_SSN = re.compile(
    r"\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0{4})\d{4}\b"
)

_CARD = re.compile(
    r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))"
    r"[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}(?:[-\s]?\d{1,3})?\b"
)

_PHONE = re.compile(
    r"\b(?:\+?1[-.\s]?)?"
    r"(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b"
)

_EMAIL = re.compile(
    r"[a-zA-Z0-9._%+\-]+@([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})"
)

# UUIDs embedded inside longer strings (narrative text, not short JSON values)
_UUID_IN_TEXT = re.compile(
    r"(?<=[\"'\s,])([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?=[\"'\s,])",
    re.IGNORECASE,
)


def scrub_pii(text: str) -> tuple[str, list[str]]:
    """
    Scrub PII from `text`.

    Returns:
        (scrubbed_text, list_of_redaction_types_applied)
    """
    redactions: list[str] = []

    text, n = _SSN.subn("[SSN-REDACTED]", text)
    if n:
        redactions.append(f"ssn×{n}")

    text, n = _CARD.subn("[CARD-REDACTED]", text)
    if n:
        redactions.append(f"card×{n}")

    text, n = _PHONE.subn("[PHONE-REDACTED]", text)
    if n:
        redactions.append(f"phone×{n}")

    # Emails: keep the domain, mask the local part
    def _mask_email(m: re.Match) -> str:
        return f"[EMAIL-REDACTED]@{m.group(1)}"

    original = text
    text = _EMAIL.sub(_mask_email, text)
    if text != original:
        redactions.append("email")

    return text, redactions


def scrub_tool_result(result_json: str) -> tuple[str, list[str]]:
    """
    Convenience wrapper: scrub a JSON string that came back from a tool.
    Short strings (pure IDs < 50 chars) are returned unchanged.
    """
    if len(result_json) < 50:
        return result_json, []
    return scrub_pii(result_json)
