# Financial Compliance Agent System

A production-grade AI agent that autonomously analyses financial transactions, detects anomalies using a deterministic rules engine, retrieves compliance policies via RAG (Retrieval-Augmented Generation), and produces structured compliance reports — all running locally in Docker with a single command.

---

## What It Does

You POST a plain-English task:

```json
{
  "account_id": "ACC-0001",
  "description": "Review recent transactions and flag any compliance issues"
}
```

The agent handles everything:

1. Fetches the account's transactions from PostgreSQL
2. Runs a Python rules engine to detect anomalies with real database UUIDs (no hallucination)
3. Retrieves relevant compliance policies via semantic vector search (pgvector)
4. Sends findings to an LLM to write the narrative analysis
5. Validates output against a Pydantic schema
6. Auto-escalates critical anomalies to the compliance queue
7. Saves a full audit trail of every step

The API returns a `task_id` immediately. You poll `GET /tasks/{id}` for the result.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    docker-compose                        │
│                                                         │
│  Client → FastAPI (:8000) → Redis Streams → Worker      │
│                ↓                               ↓        │
│           PostgreSQL ←─────────────────────────┘        │
│           + pgvector                                     │
│                                                         │
│  Worker → Ollama/OpenAI (host machine, external)        │
└─────────────────────────────────────────────────────────┘
```

| Service    | Image                      | Port  | Role                                |
|------------|----------------------------|-------|-------------------------------------|
| `postgres` | `pgvector/pgvector:pg17`   | 5433  | Primary DB + vector store           |
| `redis`    | `redis:7-alpine`           | 6380  | Task queue (Redis Streams)          |
| `api`      | Built from Dockerfile      | 8000  | FastAPI — accepts requests          |
| `worker`   | Built from Dockerfile      | —     | Agent loop — processes tasks        |

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Mac/Windows) or Docker Engine + Compose plugin (Linux)
- [Ollama](https://ollama.com) **or** an OpenAI API key
- `make` (comes with Xcode tools on Mac; `sudo apt install make` on Ubuntu)
- Git

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/your-org/financial-agent-system
cd financial-agent-system
```

### 2. Choose your LLM

**Option A — Ollama (free, local, no API key needed)**

Install Ollama from [ollama.com](https://ollama.com), then pull the models:

```bash
ollama pull llama3.2:3b    # agent reasoning
ollama pull all-minilm     # policy embeddings
```

The default `.env.docker` is already configured for Ollama — no changes needed.

**Option B — OpenAI (faster, better quality)**

Edit `.env.docker`:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

> Note: If using OpenAI you still need Ollama running for `all-minilm` embeddings (used by `make seed`), unless you adapt the embedding step to use OpenAI's embedding API.

### 3. Build Docker images

```bash
make build
```

This builds the `api`, `worker`, and `seed` service images. First build takes 3–5 minutes as it installs all Python dependencies.

### 4. Start all services

```bash
make up
```

Services start with health checks. The API is ready when you see it listed as `healthy` in `make ps`.

### 5. Seed the database

```bash
make seed
```

This runs two scripts inside Docker:

- `seed_data.py` — creates 50 synthetic accounts and 5,000 transactions with realistic anomalies
- `seed_policies.py` — chunks compliance policy markdown files, generates embeddings via Ollama, and stores them in pgvector

> Seeding takes 2–10 minutes depending on your machine (Ollama embedding generation is the slow step).

### 6. Verify everything is up

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "database": {"status": "ok", "version": "PostgreSQL 17.x ..."},
  "environment": "development"
}
```

### 7. Submit your first task

```bash
curl -s -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"account_id": "ACC-0001", "description": "Review recent transactions and flag any anomalies"}' \
  | python3 -m json.tool
```

You will receive a `task_id`. Poll for results (takes 15–60 seconds depending on your LLM):

```bash
curl -s http://localhost:8000/tasks/<task-id> | python3 -m json.tool
```

---

## Interfaces

| URL | Description |
|-----|-------------|
| `http://localhost:8000/dashboard` | Live HTML dashboard — task history, open escalations |
| `http://localhost:8000/metrics`   | Prometheus metrics endpoint                         |
| `http://localhost:8000/health`    | Health check                                        |
| `http://localhost:8000/docs`      | Auto-generated OpenAPI / Swagger UI                 |

Open `docs/project-guide.html` in your browser for a full visual walkthrough of the architecture.

---

## API Reference

### POST /tasks

Submit a new analysis task.

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"account_id": "ACC-0042", "description": "Flag any unusual transactions in the last 90 days"}'
```

Response:

```json
{
  "task_id": "018f2a4b-3c1d-7e8f-9a0b-1c2d3e4f5a6b",
  "status": "pending",
  "message": "Task queued — poll GET /tasks/{id} for status and result"
}
```

### GET /tasks/{id}

Poll for task status and result.

Status progression: `pending` → `running` → `completed` (or `failed`)

```json
{
  "id": "018f2a4b-...",
  "status": "completed",
  "result": {
    "anomalies": [
      {
        "transaction_id": "a1b2c3d4-...",
        "type": "structuring",
        "severity": "high",
        "amount": 9450.00,
        "explanation": "Transaction of $9,450 falls within the structuring range..."
      }
    ],
    "summary": "Account ACC-0042 shows 2 anomalies requiring compliance review.",
    "risk_level": "high",
    "policies_cited": ["AML Structuring Thresholds § 3.1"]
  },
  "total_steps": 5,
  "agent_model": "llama3.2:3b",
  "created_at": "2025-01-15T10:23:45Z",
  "completed_at": "2025-01-15T10:24:12Z"
}
```

### GET /tasks/{id}/audit

Full decision audit trail — every tool call and LLM step with timing.

### GET /tasks/escalations/open

All open (unresolved) critical escalations sorted by severity. Intended for the compliance team's review queue.

---

## Make Commands

| Command | Description |
|---------|-------------|
| `make up` | Start all services in the background |
| `make down` | Stop and remove containers |
| `make build` | Rebuild Docker images from scratch |
| `make seed` | Seed accounts, transactions, and policy embeddings |
| `make logs` | Follow logs from all containers |
| `make logs-api` | Follow API container logs only |
| `make logs-w` | Follow worker container logs only |
| `make ps` | Show running container status |
| `make shell` | Open a bash shell inside the API container |
| `make test` | Run the full pytest test suite (local Python required) |
| `make clean` | ⚠️ Remove all volumes — wipes database data |

---

## Project Structure

```
financial-agent-system/
├── src/
│   ├── agent/
│   │   ├── loop.py           # Core agent reasoning loop (up to 8 steps)
│   │   ├── pre_analyzer.py   # Deterministic rules engine (anti-hallucination)
│   │   └── prompts.py        # System prompt
│   ├── api/
│   │   ├── main.py           # FastAPI app, lifespan, routes
│   │   └── routes/
│   │       ├── tasks.py      # POST/GET /tasks endpoints
│   │       ├── health.py     # GET /health
│   │       └── dashboard.py  # GET /dashboard (HTML)
│   ├── db/
│   │   └── connection.py     # asyncpg connection pool
│   ├── events/
│   │   ├── producer.py       # Redis Streams publisher
│   │   ├── consumer.py       # Redis Streams consumer group
│   │   └── worker.py         # Background worker entrypoint
│   ├── guardrails/
│   │   ├── allowlist.py      # Read-before-write enforcement
│   │   ├── rate_limiter.py   # Per-task write operation caps
│   │   ├── pii_scrubber.py   # Strip SSN, CC, phone before LLM
│   │   ├── output_validator.py # Pydantic schema validation
│   │   └── escalation.py     # Auto-escalate critical findings
│   ├── llm/
│   │   ├── adapter.py        # Unified LLM interface
│   │   ├── ollama.py         # Ollama backend
│   │   └── openai.py         # OpenAI backend
│   ├── models/               # Pydantic models (task, transaction, anomaly...)
│   ├── observability/
│   │   ├── logging.py        # Structured JSON logger
│   │   └── metrics.py        # DB-backed Prometheus metrics
│   ├── rag/
│   │   ├── chunker.py        # Split markdown policy files
│   │   ├── embeddings.py     # Generate vector embeddings
│   │   └── retriever.py      # pgvector similarity search
│   └── tools/
│       ├── registry.py       # Tool definitions + dispatcher
│       ├── transactions.py   # get_account_transactions
│       ├── anomaly.py        # get_flagged_transactions
│       ├── customer.py       # get_account_details
│       └── policy.py         # search_compliance_policies
├── config/
│   └── policies/             # Compliance policy markdown files
│       ├── aml_thresholds.md
│       ├── velocity_checks.md
│       ├── geographic_risk.md
│       ├── structuring_detection.md
│       └── customer_communication.md
├── infrastructure/
│   └── init.sql              # Full PostgreSQL schema
├── scripts/
│   ├── seed_data.py          # Generate 50 accounts + 5,000 transactions
│   └── seed_policies.py      # Chunk + embed compliance policies
├── tests/
│   ├── unit/
│   │   ├── test_pre_analyzer.py  # 30+ tests for all 4 rules
│   │   └── test_guardrails.py    # Tests for all 5 guardrail layers
│   └── integration/
│       └── test_api.py           # 14 API endpoint tests
├── docs/
│   └── project-guide.html    # Visual walkthrough (open in browser)
├── Dockerfile                # Multi-stage build, non-root user
├── docker-compose.yml        # 4-service stack
├── docker-entrypoint.sh      # Postgres readiness check
├── .env.docker               # Docker environment variables
├── .dockerignore
├── Makefile
└── pyproject.toml
```

---

## How Anomaly Detection Works

The system uses a **hybrid approach** to prevent LLM hallucination:

1. **Python rules engine runs first** — detects anomalies with guaranteed real database UUIDs
2. **Findings injected into LLM context** — the LLM only writes narrative, never detects
3. **Transaction ID anchor** — after fetching transactions, the exact valid IDs are listed in a user message so the LLM cannot invent values
4. **Temperature = 0** — no randomness in LLM output
5. **Output validator** — Pydantic schema rejects any response containing unknown transaction IDs

The four detection rules in `src/agent/pre_analyzer.py`:

| Rule | Trigger | Severity |
|------|---------|----------|
| Structuring | Transaction amount $8,000–$9,999 | high |
| Velocity | More than 5 transactions in 24 hours | medium |
| Geographic risk | Transfer to NG, IR, KP, SY, CU, MM, BY | high |
| Large amount | Single transaction > 3× account median | medium |

---

## Configuration

All configuration lives in `.env.docker` (Docker) or `.env` (local development).

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | `ollama` or `openai` |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama endpoint |
| `OLLAMA_MODEL` | `llama3.2:3b` | Model for agent reasoning |
| `OPENAI_API_KEY` | — | Required if `LLM_PROVIDER=openai` |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `AGENT_MAX_STEPS` | `8` | Maximum tool-call steps per task |
| `DATABASE_URL` | `postgresql://agent:agent@postgres:5432/financial_agent` | Postgres DSN |
| `REDIS_URL` | `redis://redis:6379` | Redis connection URL |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## Running Tests

The test suite requires a local Python environment (not Docker):

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Unit tests only (no database required)
pytest tests/unit/ -v

# With coverage report
pytest tests/ --cov=src --cov-report=term-missing
```

The test suite has 71 tests: 30+ unit tests for the pre-analyzer rules, tests for all 5 guardrail layers, and 14 API integration tests (3 are skipped without a live database).

---

## Switching to OpenAI

For faster, higher-quality results in demos or production, switch from Ollama to OpenAI:

1. Edit `.env.docker`:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini
```

2. Restart the worker (no rebuild needed):

```bash
docker compose restart worker
```

OpenAI does not require the embedding step to change — policy embeddings are generated once during `make seed` and stored in Postgres.

---

## Troubleshooting

**`make seed` fails with "No markdown files found"**
The `config/` directory was not copied into the Docker image. Run `make build` to rebuild.

**`ModuleNotFoundError: No module named 'redis'`**
A dependency is missing. Run `make build` to reinstall all packages.

**Container unhealthy / PermissionError on `/app/src/__init__.py`**
File ownership issue — files were copied as root before the non-root `agent` user was created. Run `make build` to rebuild with the fixed Dockerfile.

**`[Errno 99] Cannot assign requested address` during seed**
The seed script is trying to reach Ollama at `localhost:11434` from inside Docker. Check that `OLLAMA_BASE_URL=http://host.docker.internal:11434` is set in `.env.docker` and that Ollama is running on your host machine.

**`No space left on device` during build**
Docker's disk cache is full. Run: `docker system prune -af --volumes` then `make build && make up && make seed`.

**Worker not processing tasks**
Check worker logs: `make logs-w`. Common cause: worker started before the API was healthy. Run `make down && make up`.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API framework | FastAPI + Uvicorn |
| Database | PostgreSQL 17 + pgvector extension |
| Message queue | Redis 7 Streams |
| LLM | Ollama (llama3.2:3b) or OpenAI (gpt-4o-mini) |
| Embeddings | Ollama all-minilm (384-dim vectors) |
| Async DB driver | asyncpg |
| Schema validation | Pydantic v2 |
| Observability | Structured JSON logging + Prometheus metrics |
| Containerisation | Docker Compose (multi-stage build) |
| Testing | pytest + pytest-asyncio (71 tests) |

---

## License

MIT License. See `LICENSE` for details.
