#!/bin/bash
# docker-entrypoint.sh — Wait for Postgres to accept connections, then start the process.
#
# Why: Docker starts containers in parallel. The API and worker must not start
# until Postgres is ready, otherwise asyncpg raises "connection refused".
# docker-compose depends_on with health checks handles this at the compose level,
# but this script adds a belt-and-suspenders retry loop inside the container.

set -euo pipefail

POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
MAX_RETRIES=30
RETRY_INTERVAL=2

echo "[entrypoint] Waiting for Postgres at ${POSTGRES_HOST}:${POSTGRES_PORT}..."

for i in $(seq 1 $MAX_RETRIES); do
    if python3 -c "
import socket, sys
try:
    s = socket.create_connection(('${POSTGRES_HOST}', ${POSTGRES_PORT}), timeout=2)
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        echo "[entrypoint] Postgres is ready (attempt $i)"
        break
    fi
    if [ "$i" -eq "$MAX_RETRIES" ]; then
        echo "[entrypoint] ERROR: Postgres not ready after ${MAX_RETRIES} attempts. Exiting."
        exit 1
    fi
    echo "[entrypoint] Waiting... (attempt $i/$MAX_RETRIES)"
    sleep $RETRY_INTERVAL
done

# Execute the CMD passed to the container (API server or worker)
exec "$@"
