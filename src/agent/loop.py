"""
Core agent reasoning loop — Phase 3: Guardrails + Anti-hallucination.

Anti-hallucination techniques applied:
  1. Result anchoring   — after get_account_transactions, inject a message
                          listing the EXACT valid transaction IDs so the model
                          cannot invent values.
  2. ID validation      — after the final answer, check every reported
                          transaction_id against the known-real set. If any
                          are fake, send a correction and ask the model to fix.
  3. Temperature = 0    — set in the LLM adapter options.
  4. Constrained output — system prompt lists only valid anomaly types/severities.
"""

from __future__ import annotations

import json
import time
from typing import Any
from uuid import UUID

from src.agent.pre_analyzer import analyze_transactions, build_findings_context
from src.agent.prompts import SYSTEM_PROMPT
from src.db.connection import get_connection
from src.guardrails.allowlist import GuardrailContext, GuardrailViolation
from src.guardrails.escalation import maybe_escalate
from src.guardrails.output_validator import validate_output
from src.guardrails.pii_scrubber import scrub_tool_result
from src.guardrails.rate_limiter import RateLimiter
from src.llm.adapter import LLMResponse, get_llm_adapter
from src.observability.logging import get_logger
from src.tools.registry import TOOL_DEFINITIONS, execute_tool

log = get_logger(__name__)

MAX_STEPS = 8


def _extract_transaction_ids(result: Any) -> set[str]:
    """Pull transaction IDs from a get_account_transactions result."""
    ids: set[str] = set()
    if isinstance(result, list):
        for tx in result:
            if isinstance(tx, dict):
                tid = tx.get("id") or tx.get("transaction_id")
                if tid:
                    ids.add(str(tid))
    return ids


def _anchor_message(real_ids: set[str]) -> dict:
    """
    Inject a user-turn anchor after transaction data is returned.
    Forces the model to use only real IDs in its final answer.
    """
    id_list = "\n".join(f"  - {tid}" for tid in sorted(real_ids)[:20])
    return {
        "role": "user",
        "content": (
            "IMPORTANT — valid transaction IDs from the data above:\n"
            f"{id_list}\n\n"
            "You MUST use only these exact IDs in your final JSON answer. "
            "Do not invent or modify transaction IDs."
        ),
    }


def _validate_ids(anomalies: list, real_ids: set[str]) -> list[str]:
    """Return list of fake IDs found in the model's output."""
    fake = []
    for a in anomalies:
        tid = a.get("transaction_id", "")
        if tid and tid not in real_ids:
            fake.append(tid)
    return fake


def _correction_message(fake_ids: list[str], real_ids: set[str]) -> dict:
    """Ask the model to fix fake IDs before we accept the answer."""
    id_list = "\n".join(f"  - {tid}" for tid in sorted(real_ids)[:20])
    return {
        "role": "user",
        "content": (
            f"Your answer contained invented transaction IDs: {fake_ids}\n"
            "These do not exist in the database.\n\n"
            "Valid IDs are:\n"
            f"{id_list}\n\n"
            "Please rewrite your JSON answer using only real transaction IDs from this list. "
            "If you are unsure which transaction to reference, pick the most suspicious one "
            "from the list above."
        ),
    }


async def run_agent(
    task_id: UUID,
    description: str,
    account_id: str | None = None,
) -> dict[str, Any]:
    """
    Run the agent loop for a given task.
    Returns the validated, structured result dict.
    Updates the tasks table on completion/failure.
    """
    llm = get_llm_adapter()

    # Prepend the real account_id so the agent never guesses it
    user_content = description
    if account_id:
        user_content = f"Account ID: {account_id}\n\n{description}"

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    allowlist = GuardrailContext()
    rate_limiter = RateLimiter()

    step = 0
    final_result: dict[str, Any] = {}
    real_tx_ids: set[str] = set()       # populated after get_account_transactions
    pre_findings: list[dict] = []       # rules-based findings injected into context
    task_start = time.monotonic()

    log.info("task_started", task_id=str(task_id), account_id=account_id)
    await _update_task_status(task_id, "running")

    try:
        while step < MAX_STEPS:
            step += 1
            log.info("agent_step", task_id=str(task_id), step=step, max_steps=MAX_STEPS)

            t0 = time.monotonic()
            response: LLMResponse = await llm.complete(messages, tools=TOOL_DEFINITIONS)
            duration_ms = int((time.monotonic() - t0) * 1000)

            await _log_audit(
                task_id=task_id,
                step_number=step,
                action_type="llm_call",
                action_name=None,
                input={"messages_count": len(messages)},
                output={
                    "content": response.content,
                    "tool_calls_count": len(response.tool_calls),
                },
                reasoning=response.content,
                duration_ms=duration_ms,
                status="success",
            )

            # ── Tool call branch ───────────────────────────────────────────────
            if response.is_tool_call:
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc.call_id or f"call_{step}_{i}",
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                # Groq requires arguments as a JSON *string*, not a dict
                                "arguments": (
                                    tc.arguments
                                    if isinstance(tc.arguments, str)
                                    else json.dumps(tc.arguments)
                                ),
                            },
                        }
                        for i, tc in enumerate(response.tool_calls)
                    ],
                })

                for i, tool_call in enumerate(response.tool_calls):
                    log.info("tool_call", task_id=str(task_id), step=step,
                             tool=tool_call.name, tool_args=tool_call.arguments)

                    # ── Guardrail checks ───────────────────────────────────────
                    guardrail_error: str | None = None
                    try:
                        allowlist.check(tool_call.name)
                        rate_limiter.check(tool_call.name)
                    except GuardrailViolation as gv:
                        guardrail_error = str(gv)
                        log.warning("guardrail_blocked", task_id=str(task_id),
                                    tool=tool_call.name, reason=guardrail_error)

                    if guardrail_error:
                        result = {"error": guardrail_error, "guardrail_violation": True}
                        tool_status = "blocked"
                        tool_duration_ms = 0
                    else:
                        t1 = time.monotonic()
                        try:
                            result = await execute_tool(tool_call.name, tool_call.arguments)
                            tool_status = "success"
                            allowlist.record(tool_call.name)
                            rate_limiter.record(tool_call.name)
                        except Exception as exc:
                            result = {"error": str(exc)}
                            tool_status = "failed"
                            log.error("tool_error", task_id=str(task_id),
                                      tool=tool_call.name, error=str(exc))
                        tool_duration_ms = int((time.monotonic() - t1) * 1000)

                    log.info("tool_result", task_id=str(task_id), step=step,
                             tool=tool_call.name, status=tool_status,
                             duration_ms=tool_duration_ms)

                    # ── PII scrubbing ──────────────────────────────────────────
                    result_str = json.dumps(result, default=str)
                    result_str, redactions = scrub_tool_result(result_str)
                    if redactions:
                        log.info("pii_scrubbed", task_id=str(task_id),
                                 tool=tool_call.name, redactions=redactions)

                    # Keep context small — fewer tokens = faster next LLM call
                    if len(result_str) > 1500:
                        result_str = result_str[:1500] + "... [truncated]"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.call_id or f"call_{step}_{i}",
                        "content": result_str,
                    })

                    # ── Anti-hallucination: rules analysis + anchor ────────────
                    if tool_call.name == "get_account_transactions" and tool_status == "success":
                        # Tool returns {"transactions": [...], ...} — unwrap the list
                        if isinstance(result, dict) and "transactions" in result:
                            tx_list = result["transactions"]
                        elif isinstance(result, list):
                            tx_list = result
                        else:
                            tx_list = []
                        real_tx_ids = _extract_transaction_ids(tx_list)

                        # Run Python rules engine — 100% reliable ID extraction
                        pre_findings = analyze_transactions(tx_list)
                        ctx = build_findings_context(
                            account_id or "", tx_list, pre_findings
                        )
                        messages.append({"role": "user", "content": ctx})
                        log.info("pre_analysis_complete", task_id=str(task_id),
                                 transactions=len(tx_list), findings=len(pre_findings),
                                 types=[f["anomaly_type"] for f in pre_findings])

                    await _log_audit(
                        task_id=task_id,
                        step_number=step,
                        action_type="tool_call",
                        action_name=tool_call.name,
                        input=tool_call.arguments,
                        output=(
                            result if isinstance(result, dict)
                            else {"result": str(result)}
                        ),
                        duration_ms=tool_duration_ms,
                        status=tool_status,
                    )

            # ── Final answer branch ────────────────────────────────────────────
            elif response.is_final_answer:
                log.info("final_answer_received", task_id=str(task_id), step=step)
                messages.append({"role": "assistant", "content": response.content})

                raw = _extract_json(response.content or "") or response.content or {}

                # ── Anti-hallucination: ID validation ──────────────────────────
                if real_tx_ids and isinstance(raw, dict):
                    anomalies = raw.get("anomalies_found", [])
                    fake_ids = _validate_ids(anomalies, real_tx_ids)
                    if fake_ids and step < MAX_STEPS - 1:
                        log.warning("fake_ids_detected", task_id=str(task_id),
                                    fake_ids=fake_ids)
                        messages.append(_correction_message(fake_ids, real_tx_ids))
                        continue  # loop again for the model to fix its answer

                # ── Override with pre-findings (rules engine is authoritative) ──
                if isinstance(raw, dict) and pre_findings:
                    raw["anomalies_found"] = pre_findings
                    log.info("pre_findings_injected", task_id=str(task_id),
                             count=len(pre_findings))
                elif isinstance(raw, dict) and not pre_findings:
                    raw["anomalies_found"] = []
                    log.info("no_anomalies", task_id=str(task_id))

                # ── Output validation ──────────────────────────────────────────
                try:
                    validated = validate_output(raw)
                    final_result = validated.to_dict()
                    log.info("output_validated", task_id=str(task_id),
                             anomaly_count=len(validated.anomalies_found),
                             requires_escalation=validated.requires_escalation)
                except Exception as ve:
                    log.error("output_validation_failed", task_id=str(task_id),
                              error=str(ve))
                    final_result = (
                        raw if isinstance(raw, dict)
                        else {"summary": str(raw), "raw": True}
                    )
                    validated = None

                # ── Auto-escalation ────────────────────────────────────────────
                if validated and validated.requires_escalation:
                    esc_id = await maybe_escalate(task_id, validated, account_id)
                    if esc_id:
                        final_result["escalation_id"] = str(esc_id)

                final_result["_guardrails"] = {
                    "tool_counts": rate_limiter.counts(),
                    "call_history": allowlist.call_history,
                }

                break

            else:
                final_result = {"summary": "Agent produced no output", "error": True}
                break

        else:
            final_result = {
                "summary": f"Agent reached max steps ({MAX_STEPS}) without completing",
                "truncated": True,
                "_guardrails": {
                    "tool_counts": rate_limiter.counts(),
                    "call_history": allowlist.call_history,
                },
            }

        duration_s = time.monotonic() - task_start
        log.info("task_completed", task_id=str(task_id), steps=step,
                 duration_s=round(duration_s, 1),
                 anomaly_count=len(pre_findings))
        await _update_task_status(task_id, "completed", result=final_result, total_steps=step)
        return final_result

    except Exception as exc:
        log.exception("task_failed", task_id=str(task_id), steps=step, error=repr(exc))
        error_result = {"error": repr(exc), "summary": "Agent loop failed"}
        await _update_task_status(task_id, "failed", result=error_result, total_steps=step)
        raise


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict[str, Any] | None:
    import re
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


async def _update_task_status(
    task_id: UUID,
    status: str,
    result: dict[str, Any] | None = None,
    total_steps: int = 0,
) -> None:
    async with get_connection() as conn:
        if result is not None:
            await conn.execute(
                """
                UPDATE tasks
                SET status = $1, result = $2::jsonb, total_steps = $3,
                    completed_at = NOW()
                WHERE id = $4
                """,
                status, json.dumps(result), total_steps, task_id,
            )
        else:
            await conn.execute(
                "UPDATE tasks SET status = $1 WHERE id = $2",
                status, task_id,
            )


async def _log_audit(
    task_id: UUID,
    step_number: int,
    action_type: str,
    action_name: str | None,
    input: dict[str, Any] | None = None,
    output: dict[str, Any] | None = None,
    reasoning: str | None = None,
    duration_ms: int | None = None,
    status: str = "success",
) -> None:
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO audit_log
                (task_id, step_number, action_type, action_name,
                 input, output, reasoning, duration_ms, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            task_id, step_number, action_type, action_name,
            json.dumps(input) if input else None,
            json.dumps(output, default=str) if output else None,
            reasoning, duration_ms, status,
        )
