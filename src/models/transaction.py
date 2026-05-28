"""Pydantic models for Transaction and Account."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class AccountType(str, Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT = "credit"


class AccountStatus(str, Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


class TransactionDirection(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"


# ── Account ───────────────────────────────────────────────────────────────────

class AccountResponse(BaseModel):
    id: UUID
    customer_name: str
    account_type: AccountType
    status: AccountStatus
    risk_score: float
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Transaction ───────────────────────────────────────────────────────────────

class TransactionResponse(BaseModel):
    id: UUID
    account_id: UUID
    amount: float
    currency: str
    direction: TransactionDirection
    counterparty: str | None
    category: str | None
    country_code: str | None
    is_flagged: bool
    flag_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
