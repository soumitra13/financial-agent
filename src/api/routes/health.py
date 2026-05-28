"""GET /health — liveness + DB connectivity check."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.db.connection import health_check

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    database: dict
    environment: str


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """
    Returns service health.
    - status: "ok" if all dependencies are reachable, else "degraded"
    - database: connection info from asyncpg
    """
    from src.config import get_settings
    settings = get_settings()

    db = await health_check()
    overall = "ok" if db["status"] == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        database=db,
        environment=settings.environment,
    )
