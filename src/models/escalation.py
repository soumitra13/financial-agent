"""Pydantic models for Escalation."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from src.models.anomaly import Severity


class EscalationCreate(BaseModel):
    task_id: UUID
    reason: str
    agent_analysis: dict[str, Any] | None = None
    severity: Severity = Severity.MEDIUM


class EscalationReview(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected)$")
    reviewer_notes: str | None = None


class EscalationResponse(BaseModel):
    id: UUID
    task_id: UUID
    reason: str
    agent_analysis: dict[str, Any] | None
    severity: Severity
    status: str
    reviewer_notes: str | None
    resolved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
