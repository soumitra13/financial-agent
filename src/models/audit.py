"""Pydantic models for AuditLog entries."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ActionType(str, Enum):
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    GUARDRAIL_CHECK = "guardrail_check"
    ESCALATION = "escalation"
    OUTPUT_VALIDATION = "output_validation"


class AuditEntryResponse(BaseModel):
    id: int
    task_id: UUID
    step_number: int
    action_type: ActionType
    action_name: str | None
    input: dict[str, Any] | None
    output: dict[str, Any] | None
    reasoning: str | None
    duration_ms: int | None
    status: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
