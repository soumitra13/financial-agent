# ── Stage 1: dependency layer ──────────────────────────────────────────────────
# Separate layer so rebuilds after source-only changes skip pip install.
FROM python:3.14-slim AS deps

WORKDIR /app

# Build tools needed by some Python packages (asyncpg compiles a C extension)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
# Install the package in editable mode so src/ is importable as a package.
# --no-cache-dir keeps the layer small.
RUN pip install --no-cache-dir -e ".[dev]"


# ── Stage 2: runtime image ─────────────────────────────────────────────────────
FROM deps AS runtime

WORKDIR /app

# Copy application source
COPY src/ src/
COPY infrastructure/ infrastructure/
COPY scripts/ scripts/
COPY config/ config/

# Non-root user for security; chown all app files so agent can read them
RUN useradd --create-home --shell /bin/bash agent && chown -R agent:agent /app

# Entrypoint script handles waiting for Postgres before starting
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER agent

# Expose API port
EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]

# Default: API server
# Override in docker-compose for the worker: command: python3 -m src.events.worker
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
