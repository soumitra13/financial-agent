"""
metrics.py — DB-backed Prometheus metrics for the Financial Agent System.

Why DB-backed instead of in-process counters:
  The agent loop runs in the worker process; the API serves /metrics.
  In-process prometheus_client counters live in per-process memory and are
  never shared, so worker increments never appear in the API's /metrics.

  Solution: query Postgres on each scrape. Postgres IS the shared state.
  This is accurate, zero-lag, and requires no push-gateway or sidecar.

Metrics exposed:
  financial_agent_tasks_total{status}
  financial_agent_task_duration_seconds (histogram, computed from DB)
  financial_agent_anomalies_total{anomaly_type,severity}
  financial_agent_agent_steps_total
  financial_agent_tool_calls_total{tool,status}
  financial_agent_llm_calls_total
  financial_agent_escalations_total{severity}
"""

from __future__ import annotations


async def generate_metrics() -> str:
    """
    Query the DB and return Prometheus exposition-format text.
    Called on each GET /metrics request.
    """
    from src.db.connection import get_connection

    async with get_connection() as conn:
        # ── Task counts by status ──────────────────────────────────────────────
        task_rows = await conn.fetch(
            "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"
        )
        # ── Task duration (completed tasks only) ───────────────────────────────
        duration_rows = await conn.fetch(
            """
            SELECT
                EXTRACT(EPOCH FROM (completed_at - created_at)) AS duration_s
            FROM tasks
            WHERE status = 'completed' AND completed_at IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1000
            """
        )
        # ── Total agent steps ──────────────────────────────────────────────────
        steps_row = await conn.fetchrow(
            "SELECT COALESCE(SUM(total_steps), 0) AS total FROM tasks"
        )
        # ── Anomaly breakdown from JSONB result ────────────────────────────────
        anomaly_rows = await conn.fetch(
            """
            SELECT
                a->>'anomaly_type' AS anomaly_type,
                a->>'severity'     AS severity,
                COUNT(*)           AS n
            FROM tasks,
                 jsonb_array_elements(
                     COALESCE(result->'anomalies_found', '[]'::jsonb)
                 ) AS a
            WHERE result IS NOT NULL
            GROUP BY 1, 2
            """
        )
        # ── Tool calls from audit_log ──────────────────────────────────────────
        tool_rows = await conn.fetch(
            """
            SELECT action_name AS tool, status, COUNT(*) AS n
            FROM audit_log
            WHERE action_type = 'tool_call' AND action_name IS NOT NULL
            GROUP BY 1, 2
            """
        )
        # ── LLM calls ─────────────────────────────────────────────────────────
        llm_row = await conn.fetchrow(
            "SELECT COUNT(*) AS n FROM audit_log WHERE action_type = 'llm_call'"
        )
        # ── Escalations ───────────────────────────────────────────────────────
        esc_rows = await conn.fetch(
            "SELECT severity, COUNT(*) AS n FROM escalations GROUP BY severity"
        )

    lines: list[str] = []

    def counter(name: str, help_text: str, labels: dict[str, str], value: float) -> None:
        label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
        metric_name = f"financial_agent_{name}"
        lines.append(f"# HELP {metric_name} {help_text}")
        lines.append(f"# TYPE {metric_name} counter")
        lines.append(f"{metric_name}{{{label_str}}} {value}")

    def gauge(name: str, help_text: str, value: float, labels: dict[str, str] | None = None) -> None:
        metric_name = f"financial_agent_{name}"
        lines.append(f"# HELP {metric_name} {help_text}")
        lines.append(f"# TYPE {metric_name} gauge")
        label_str = ""
        if labels:
            label_str = "{" + ",".join(f'{k}="{v}"' for k, v in labels.items()) + "}"
        lines.append(f"{metric_name}{label_str} {value}")

    # ── tasks_total ────────────────────────────────────────────────────────────
    lines.append("# HELP financial_agent_tasks_total Total tasks by final status")
    lines.append("# TYPE financial_agent_tasks_total counter")
    for r in task_rows:
        lines.append(f'financial_agent_tasks_total{{status="{r["status"]}"}} {r["n"]}')

    # ── task_duration_seconds (histogram approximation) ────────────────────────
    durations = [float(r["duration_s"]) for r in duration_rows if r["duration_s"] is not None]
    buckets = [30, 60, 120, 180, 300, 600, 900]
    lines.append("# HELP financial_agent_task_duration_seconds End-to-end task time in seconds")
    lines.append("# TYPE financial_agent_task_duration_seconds histogram")
    for b in buckets:
        count = sum(1 for d in durations if d <= b)
        lines.append(f'financial_agent_task_duration_seconds_bucket{{le="{float(b)}"}} {count}')
    lines.append(f'financial_agent_task_duration_seconds_bucket{{le="+Inf"}} {len(durations)}')
    lines.append(f'financial_agent_task_duration_seconds_count {len(durations)}')
    lines.append(f'financial_agent_task_duration_seconds_sum {sum(durations):.3f}')

    # ── agent_steps_total ──────────────────────────────────────────────────────
    lines.append("# HELP financial_agent_agent_steps_total Total reasoning steps across all tasks")
    lines.append("# TYPE financial_agent_agent_steps_total counter")
    lines.append(f'financial_agent_agent_steps_total {int(steps_row["total"])}')

    # ── anomalies_total ────────────────────────────────────────────────────────
    lines.append("# HELP financial_agent_anomalies_total Anomalies detected by rules engine")
    lines.append("# TYPE financial_agent_anomalies_total counter")
    for r in anomaly_rows:
        if r["anomaly_type"]:
            lines.append(
                f'financial_agent_anomalies_total{{anomaly_type="{r["anomaly_type"]}",'
                f'severity="{r["severity"] or "unknown"}"}} {r["n"]}'
            )

    # ── tool_calls_total ───────────────────────────────────────────────────────
    lines.append("# HELP financial_agent_tool_calls_total Tool calls by name and status")
    lines.append("# TYPE financial_agent_tool_calls_total counter")
    for r in tool_rows:
        lines.append(
            f'financial_agent_tool_calls_total{{tool="{r["tool"]}",'
            f'status="{r["status"]}"}} {r["n"]}'
        )

    # ── llm_calls_total ────────────────────────────────────────────────────────
    lines.append("# HELP financial_agent_llm_calls_total Total LLM inference calls")
    lines.append("# TYPE financial_agent_llm_calls_total counter")
    lines.append(f'financial_agent_llm_calls_total {int(llm_row["n"])}')

    # ── escalations_total ─────────────────────────────────────────────────────
    lines.append("# HELP financial_agent_escalations_total Escalations raised by severity")
    lines.append("# TYPE financial_agent_escalations_total counter")
    for r in esc_rows:
        lines.append(f'financial_agent_escalations_total{{severity="{r["severity"]}"}} {r["n"]}')

    lines.append("")  # trailing newline required by exposition format
    return "\n".join(lines)
