"""Pydantic models for AnomalyReport — structured agent output."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class AnomalyType(StrEnum):
    VELOCITY = "velocity"
    STRUCTURING = "structuring"
    GEOGRAPHIC = "geographic"
    AMOUNT = "amount"
    ROUND_NUMBER = "round_number"
    OUT_OF_PATTERN = "out_of_pattern"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyReport(BaseModel):
    """Validated output the agent produces when flagging a transaction."""

    transaction_id: UUID
    anomaly_type: AnomalyType
    severity: Severity
    evidence: str = Field(..., description="What the agent observed")
    policy_references: list[str] = Field(
        default_factory=list,
        description="Policy titles or IDs that apply",
    )
    recommended_action: str = Field(
        ...,
        description="What the agent recommends: monitor / flag / escalate",
    )
