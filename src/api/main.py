"""
FastAPI application entry point.

Lifespan:
  startup  → initialise asyncpg connection pool
  shutdown → gracefully close the pool
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from src.api.routes import health, tasks, dashboard
from src.api.routes import auth as auth_routes
from src.auth import keys as key_svc
from src.config import get_settings
from src.db.connection import close_pool, init_pool
from src.observability.logging import configure_logging, get_logger
from src.observability.metrics import generate_metrics

configure_logging()
log = get_logger(__name__)


async def _bootstrap_first_key() -> None:
    """
    If no API keys exist yet, generate one and print it clearly to stdout.
    This runs once on first startup — the operator copies the key from logs.
    """
    count = await key_svc.key_count()
    if count == 0:
        record = await key_svc.create_key(name="bootstrap")
        print("\n" + "=" * 60, flush=True)
        print("  🔑  INITIAL API KEY GENERATED (shown once only)", flush=True)
        print("=" * 60, flush=True)
        print(f"  Key : {record['key']}", flush=True)
        print(f"  Name: {record['name']}", flush=True)
        print("  Add X-API-Key: <key> to all API requests.", flush=True)
        print("=" * 60 + "\n", flush=True)
        log.info("bootstrap_key_created", key_name=record["name"])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown of shared resources."""
    settings = get_settings()

    # ── Startup ───────────────────────────────────────────────────────────────
    await init_pool(
        dsn=settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
    )
    log.info("db_pool_ready", environment=settings.environment)

    # Generate first API key if none exist
    await _bootstrap_first_key()

    yield  # app is running

    # ── Shutdown ──────────────────────────────────────────────────────────────
    await close_pool()
    log.info("db_pool_closed")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Financial Agent System",
        description=(
            "Production-style agentic AI that analyses transactions, "
            "flags anomalies, and escalates with full audit logging."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Development: allow all origins (local UI dev)
    # Production: allow only the origins listed in CORS_ORIGINS env var
    if settings.environment == "development":
        cors_origins = ["*"]
    else:
        cors_origins = (
            [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
            if settings.cors_origins
            else []
        )

    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    # Public routes (no auth required)
    app.include_router(health.router)
    app.include_router(dashboard.router)

    # Protected routes (require X-API-Key header)
    from src.auth.dependency import require_api_key
    from fastapi import Depends
    app.include_router(tasks.router, dependencies=[Depends(require_api_key)])
    app.include_router(auth_routes.router, dependencies=[Depends(require_api_key)])

    # ── Observability endpoints ───────────────────────────────────────────────
    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics() -> Response:
        """Prometheus scrape endpoint — DB-backed, accurate across processes."""
        body = await generate_metrics()
        return Response(
            content=body,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return app


app = create_app()


if __name__ == "__main__":
    import os
    import uvicorn

    # Railway (and other PaaS) injects PORT as an env var.
    # Reading it here avoids shell-expansion issues with exec-form Docker CMD.
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=port, log_level="info")
