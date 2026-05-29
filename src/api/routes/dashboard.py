"""
dashboard.py — Server-rendered HTML task dashboard.

GET /dashboard — Shows recent tasks, anomaly stats, system health.
Auto-refreshes every 30 seconds. No JS framework, no build step.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.db.connection import get_connection

router = APIRouter(tags=["dashboard"])


async def _fetch_stats() -> dict[str, Any]:
    async with get_connection() as conn:
        # Recent tasks
        tasks = await conn.fetch(
            """
            SELECT id, status, total_steps, created_at, completed_at,
                   result->>'summary' AS summary,
                   jsonb_array_length(result->'anomalies_found') AS anomaly_count
            FROM tasks
            ORDER BY created_at DESC
            LIMIT 20
            """
        )

        # Status counts
        status_counts = await conn.fetch(
            "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status ORDER BY n DESC"
        )

        # Anomaly type breakdown (from JSONB)
        anomaly_types = await conn.fetch(
            """
            SELECT
                a->>'anomaly_type' AS anomaly_type,
                a->>'severity'     AS severity,
                COUNT(*)           AS n
            FROM tasks,
                 jsonb_array_elements(COALESCE(result->'anomalies_found', '[]'::jsonb)) AS a
            WHERE result IS NOT NULL
            GROUP BY 1, 2
            ORDER BY n DESC
            LIMIT 10
            """
        )

        # Open escalations
        escalations = await conn.fetch(
            """
            SELECT e.id, e.reason, e.severity, e.created_at,
                   t.id AS task_id
            FROM escalations e
            JOIN tasks t ON t.id = e.task_id
            WHERE e.status = 'pending'
            ORDER BY e.created_at DESC
            LIMIT 5
            """
        )

    return {
        "tasks": [dict(r) for r in tasks],
        "status_counts": {r["status"]: r["n"] for r in status_counts},
        "anomaly_types": [dict(r) for r in anomaly_types],
        "escalations": [dict(r) for r in escalations],
    }


def _status_badge(status: str) -> str:
    colors = {
        "completed": "#22c55e",
        "failed": "#ef4444",
        "running": "#3b82f6",
        "pending": "#f59e0b",
        "escalated": "#a855f7",
    }
    color = colors.get(status, "#6b7280")
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:12px;font-weight:600">{status}</span>'
    )


def _severity_color(severity: str) -> str:
    return {"high": "#ef4444", "critical": "#7c3aed",
            "medium": "#f59e0b", "low": "#22c55e"}.get(severity, "#6b7280")


def _render(stats: dict[str, Any]) -> str:
    tasks = stats["tasks"]
    status_counts = stats["status_counts"]
    anomaly_types = stats["anomaly_types"]
    escalations = stats["escalations"]

    total_tasks = sum(status_counts.values())
    total_anomalies = sum(
        (t.get("anomaly_count") or 0) for t in tasks
    )

    # ── Summary cards ──────────────────────────────────────────────────────────
    completed = status_counts.get("completed", 0)
    failed    = status_counts.get("failed", 0)
    running   = status_counts.get("running", 0)
    pending   = status_counts.get("pending", 0)

    cards = f"""
    <div class="cards">
      <div class="card"><div class="card-value">{total_tasks}</div><div class="card-label">Total Tasks</div></div>
      <div class="card green"><div class="card-value">{completed}</div><div class="card-label">Completed</div></div>
      <div class="card red"><div class="card-value">{failed}</div><div class="card-label">Failed</div></div>
      <div class="card blue"><div class="card-value">{running + pending}</div><div class="card-label">In Queue</div></div>
      <div class="card purple"><div class="card-value">{len(escalations)}</div><div class="card-label">Open Escalations</div></div>
      <div class="card orange"><div class="card-value">{total_anomalies}</div><div class="card-label">Anomalies (last 20)</div></div>
    </div>"""

    # ── Task table ─────────────────────────────────────────────────────────────
    rows = ""
    for t in tasks:
        task_id_short = str(t["id"])[:8]
        created = str(t["created_at"])[:16].replace("T", " ")
        anomaly_n = t.get("anomaly_count") or 0
        summary = (t.get("summary") or "—")[:80]
        steps = t.get("total_steps") or "—"
        rows += f"""
        <tr>
          <td><code title="{t['id']}">{task_id_short}</code></td>
          <td>{_status_badge(t['status'])}</td>
          <td>{steps}</td>
          <td><b style="color:{'#ef4444' if anomaly_n else '#6b7280'}">{anomaly_n}</b></td>
          <td style="color:#6b7280;font-size:13px">{summary}</td>
          <td style="color:#6b7280;font-size:12px">{created}</td>
        </tr>"""

    task_table = f"""
    <h2>Recent Tasks</h2>
    <table>
      <thead><tr>
        <th>ID</th><th>Status</th><th>Steps</th><th>Anomalies</th>
        <th>Summary</th><th>Created</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>"""

    # ── Anomaly breakdown ──────────────────────────────────────────────────────
    anomaly_rows = ""
    for a in anomaly_types:
        color = _severity_color(a["severity"])
        anomaly_rows += f"""
        <tr>
          <td>{a['anomaly_type']}</td>
          <td><span style="color:{color};font-weight:600">{a['severity']}</span></td>
          <td><b>{a['n']}</b></td>
        </tr>"""

    anomaly_section = f"""
    <h2>Anomaly Breakdown</h2>
    <table>
      <thead><tr><th>Type</th><th>Severity</th><th>Count</th></tr></thead>
      <tbody>{anomaly_rows if anomaly_rows else '<tr><td colspan="3" style="color:#6b7280">No anomalies yet</td></tr>'}</tbody>
    </table>"""

    # ── Escalations ────────────────────────────────────────────────────────────
    esc_rows = ""
    for e in escalations:
        color = _severity_color(e["severity"])
        created = str(e["created_at"])[:16].replace("T", " ")
        esc_rows += f"""
        <tr>
          <td><code>{str(e['id'])[:8]}</code></td>
          <td><span style="color:{color};font-weight:600">{e['severity']}</span></td>
          <td>{e['reason'][:80]}</td>
          <td style="color:#6b7280;font-size:12px">{created}</td>
        </tr>"""

    esc_section = f"""
    <h2>Open Escalations</h2>
    <table>
      <thead><tr><th>ID</th><th>Severity</th><th>Reason</th><th>Created</th></tr></thead>
      <tbody>{esc_rows if esc_rows else '<tr><td colspan="4" style="color:#6b7280">No open escalations</td></tr>'}</tbody>
    </table>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="30">
  <title>Financial Agent — Dashboard</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #0f172a; color: #e2e8f0; padding: 24px; }}
    h1 {{ font-size: 22px; margin-bottom: 20px; color: #f8fafc; }}
    h1 span {{ color: #64748b; font-size: 14px; font-weight: 400; margin-left: 12px; }}
    h2 {{ font-size: 16px; color: #94a3b8; margin: 28px 0 12px; text-transform: uppercase;
          letter-spacing: 0.05em; }}
    .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 8px; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 16px 20px;
             min-width: 130px; border: 1px solid #334155; }}
    .card.green {{ border-color: #22c55e44; }}
    .card.red   {{ border-color: #ef444444; }}
    .card.blue  {{ border-color: #3b82f644; }}
    .card.purple {{ border-color: #a855f744; }}
    .card.orange {{ border-color: #f59e0b44; }}
    .card-value {{ font-size: 28px; font-weight: 700; color: #f8fafc; }}
    .card-label {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; background: #1e293b;
             border-radius: 10px; overflow: hidden; border: 1px solid #334155; }}
    th {{ background: #0f172a; color: #64748b; font-size: 12px; text-transform: uppercase;
          letter-spacing: 0.05em; padding: 10px 14px; text-align: left; }}
    td {{ padding: 10px 14px; border-top: 1px solid #1e293b88;
          font-size: 14px; color: #cbd5e1; }}
    tr:hover td {{ background: #1e293b99; }}
    code {{ background: #334155; padding: 2px 6px; border-radius: 4px;
            font-family: monospace; font-size: 12px; }}
    .refresh {{ color: #334155; font-size: 12px; margin-top: 24px; }}
  </style>
</head>
<body>
  <h1>Financial Agent Dashboard <span>auto-refreshes every 30s</span></h1>
  {cards}
  {task_table}
  <div style="display:flex;gap:24px;align-items:flex-start;margin-top:4px">
    <div style="flex:1">{anomaly_section}</div>
    <div style="flex:1">{esc_section}</div>
  </div>
  <p class="refresh">Last rendered: {__import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
</body>
</html>"""


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> HTMLResponse:
    """Operational dashboard — recent tasks, anomaly breakdown, escalation queue."""
    stats = await _fetch_stats()
    html = _render(stats)
    return HTMLResponse(content=html)
