# ── Financial Agent System — Makefile ─────────────────────────────────────────
# Convenience wrappers for common Docker and dev operations.
# Usage: make <target>

.PHONY: help up down logs build shell test seed ps clean

# ── Default ───────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "Financial Agent System"
	@echo "────────────────────────────────────────────"
	@echo "  make up        Start all services"
	@echo "  make down      Stop and remove containers"
	@echo "  make build     Rebuild Docker images"
	@echo "  make logs      Follow all container logs"
	@echo "  make logs-api  Follow API logs only"
	@echo "  make logs-w    Follow worker logs only"
	@echo "  make ps        Show running containers"
	@echo "  make migrate   Run database migrations (adds new tables)"
	@echo "  make seed      Seed accounts + transactions + policies"
	@echo "  make test      Run the test suite (local Python)"
	@echo "  make shell     Open a shell in the API container"
	@echo "  make clean     Remove volumes (wipes DB data)"
	@echo ""

# ── Core lifecycle ────────────────────────────────────────────────────────────
up:
	docker compose up -d
	@echo ""
	@echo "Services starting. Check status with: make ps"
	@echo "API available at:       http://localhost:8000"
	@echo "Dashboard:              http://localhost:8000/dashboard"
	@echo "Metrics:                http://localhost:8000/metrics"
	@echo "Postgres (host port):   localhost:5433"
	@echo "Redis (host port):      localhost:6380"

down:
	docker compose down

build:
	docker compose --profile seed build --no-cache

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-w:
	docker compose logs -f worker

ps:
	docker compose ps

# ── Database ──────────────────────────────────────────────────────────────────
migrate:
	@echo "Running database migrations..."
	docker compose run --rm \
		-e POSTGRES_HOST=postgres \
		seed python3 scripts/migrate_add_api_keys.py
	@echo "Done."

seed:
	@echo "Seeding accounts + transactions..."
	docker compose run --rm \
		-e POSTGRES_HOST=postgres \
		seed python3 scripts/seed_data.py
	@echo "Seeding policy embeddings..."
	docker compose run --rm \
		-e POSTGRES_HOST=postgres \
		seed python3 scripts/seed_policies.py
	@echo "Done. Run 'make up' if services aren't running."

# ── Testing ───────────────────────────────────────────────────────────────────
test:
	pytest tests/unit/ tests/integration/ -v

# ── Dev shell ─────────────────────────────────────────────────────────────────
shell:
	docker compose exec api /bin/bash

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	@echo "⚠️  This will delete all database data. Press Ctrl+C to cancel."
	@sleep 3
	docker compose down -v
