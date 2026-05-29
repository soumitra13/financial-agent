"""Pydantic models for Task — request, response, and DB row."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


# ── Request ───────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        examples=["Review recent transactions for account ABC-123 and flag anomalies"],
    )
    account_id: str | None = Field(
        default=None,
        description="Optional account UUID to scope the task",
    )


# ── Response ──────────────────────────────────────────────────────────────────

class TaskResponse(BaseModel):
    id: UUID
    description: str
    status: TaskStatus
    result: dict[str, Any] | None = None
    agent_model: str | None = None
    total_steps: int
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class TaskCreateResponse(BaseModel):
    task_id: UUID
    status: TaskStatus
    message: str = "Task created and queued for processing"
