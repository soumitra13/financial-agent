"""
Task routes:
  POST /tasks          — create and run a task
  GET  /tasks/{id}     — get task status + result
  GET  /tasks/{id}/audit — get full audit trail
"""

from __future__ import annotations

import json as _json
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.db.connection import get_connection
from src.events.producer import publish_task
from src.models.audit import AuditEntryResponse
from src.models.task import TaskCreate, TaskCreateResponse, TaskResponse, TaskStatus


def _parse_jsonb(value) -> dict | None:
    """Safely parse a JSONB value that asyncpg may return as a dict or string."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return _json.loads(value)
        except Exception:
            return {"raw": value}
    return dict(value)


router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskResponse])
async def list_tasks(limit: int = 50) -> list[TaskResponse]:
    """Return the most recent tasks ordered by creation time."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, description, status, result, agent_model,
                   total_steps, created_at, completed_at
            FROM tasks
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [
        TaskResponse(
            id=row["id"],
            description=row["description"],
            status=TaskStatus(row["status"]),
            result=_parse_jsonb(row["result"]),
            agent_model=row["agent_model"],
            total_steps=row["total_steps"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )
        for row in rows
    ]


@router.get("/stats")
async def get_task_stats() -> dict:
    """Return aggregate task statistics for the metrics dashboard."""
    async with get_connection() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM tasks")
        completed = await conn.fetchval("SELECT COUNT(*) FROM tasks WHERE status = 'completed'")
        pending = await conn.fetchval("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
        failed = await conn.fetchval("SELECT COUNT(*) FROM tasks WHERE status = 'failed'")
        escalations = await conn.fetchval("SELECT COUNT(*) FROM escalations WHERE status = 'pending'")
        critical = await conn.fetchval("SELECT COUNT(*) FROM escalations WHERE severity = 'critical' AND status = 'pending'")
        today = await conn.fetchval(
            "SELECT COUNT(*) FROM tasks WHERE created_at >= NOW() - INTERVAL '24 hours'"
        )
        anomaly_rate = round((escalations / total * 100), 1) if total > 0 else 0
    return {
        "total": total,
        "completed": completed,
        "pending": pending,
        "failed": failed,
        "escalations_open": escalations,
        "escalations_critical": critical,
        "tasks_today": today,
        "anomaly_rate": anomaly_rate,
    }


@router.get("/escalations/open")
async def list_open_escalations_static() -> list[dict]:
    """Return all open escalations (static path — must be before /{task_id})."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT e.id, e.task_id, e.reason, e.agent_analysis,
                   e.severity, e.status, e.created_at
            FROM escalations e
            WHERE e.status = 'pending'
            ORDER BY
                CASE e.severity
                    WHEN 'critical' THEN 1
                    WHEN 'high'     THEN 2
                    WHEN 'medium'   THEN 3
                    ELSE 4
                END,
                e.created_at DESC
            """
        )
    return [
        {
            "id": str(r["id"]),
            "task_id": str(r["task_id"]),
            "reason": r["reason"],
            "agent_analysis": _parse_jsonb(r["agent_analysis"]),
            "severity": r["severity"],
            "status": r["status"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]


@router.post("", response_model=TaskCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_task(payload: TaskCreate) -> TaskCreateResponse:
    """
    Submit a new analysis task.
    Writes to Redis Stream and returns 202 immediately.
    The worker process picks it up and runs the agent.
    Poll GET /tasks/{id} for status and result.
    """
    # 1. Persist the task record
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO tasks (description, status)
            VALUES ($1, $2)
            RETURNING id, status
            """,
            payload.description,
            TaskStatus.PENDING.value,
        )

    task_id = row["id"]

    # 2. Publish to Redis Stream — returns immediately
    try:
        msg_id = publish_task(
            task_id=task_id,
            description=payload.description,
            account_id=payload.account_id,
        )
        print(f"[api] Published task {task_id} → stream msg {msg_id}", flush=True)
    except Exception as exc:
        # If Redis is down, fall back gracefully with a clear error
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Task queue unavailable: {exc}. Is Redis running?",
        )

    return TaskCreateResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message="Task queued — poll GET /tasks/{id} for status and result",
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: UUID) -> TaskResponse:
    """Return current status and result of a task."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, description, status, result, agent_model,
                   total_steps, created_at, completed_at
            FROM tasks
            WHERE id = $1
            """,
            task_id,
        )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    return TaskResponse(
        id=row["id"],
        description=row["description"],
        status=TaskStatus(row["status"]),
        result=_parse_jsonb(row["result"]),
        agent_model=row["agent_model"],
        total_steps=row["total_steps"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )


@router.get("/{task_id}/audit", response_model=list[AuditEntryResponse])
async def get_task_audit(task_id: UUID) -> list[AuditEntryResponse]:
    """Return the complete decision chain for a task."""
    async with get_connection() as conn:
        # Verify task exists
        exists = await conn.fetchval("SELECT 1 FROM tasks WHERE id = $1", task_id)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found",
            )

        rows = await conn.fetch(
            """
            SELECT id, task_id, step_number, action_type, action_name,
                   input, output, reasoning, duration_ms, status, created_at
            FROM audit_log
            WHERE task_id = $1
            ORDER BY step_number ASC
            """,
            task_id,
        )

    def _jsonb(val):
        """asyncpg may return JSONB as a dict or as a raw string — handle both."""
        if val is None:
            return None
        if isinstance(val, dict):
            return val
        try:
            import json
            return json.loads(val)
        except Exception:
            return {"raw": str(val)}

    return [
        AuditEntryResponse(
            id=r["id"],
            task_id=r["task_id"],
            step_number=r["step_number"],
            action_type=r["action_type"],
            action_name=r["action_name"],
            input=_jsonb(r["input"]),
            output=_jsonb(r["output"]),
            reasoning=r["reasoning"],
            duration_ms=r["duration_ms"],
            status=r["status"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


