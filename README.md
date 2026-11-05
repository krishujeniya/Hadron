<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg" />
    <img src="assets/logo.svg" alt="Hadron — multi-agent pull request review" width="420" />
  </picture>
</p>

# Hadron: autonomous multi-agent PR review engine

<p align="center">
  <a href="https://hadron.vercel.app"><img src="https://img.shields.io/badge/Live_Dashboard-hadron.vercel.app-000000?style=for-the-badge&logo=vercel&logoColor=white" alt="Live Dashboard" /></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/Next.js-15-000000?style=for-the-badge&logo=nextdotjs&logoColor=white" alt="Next.js 15" />
  <img src="https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/LangGraph-Stateful_Orchestration-1C3C3C?style=for-the-badge" alt="LangGraph" />
  <img src="https://img.shields.io/badge/Docker-Multi--Stage_Containers-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/PostgreSQL-pgvector-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL pgvector" />
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License" />
</p>

> Hadron reviews pull requests with four specialist sub-agents running in parallel: security, code quality, test coverage, and documentation. It fetches relevant repository context with vector search, scores finding confidence, and posts inline review comments to the pull request. Borderline findings are routed to a human approval queue.

---

The Hadron identity represents four review specialists converging on one shared decision. See the [brand system](docs/design/BRAND.md) for the SVG masters, color roles, favicon variants, and reproducible PNG exports.

---

## Key features

- **Multi-agent parallel review.** Four autonomous specialist agents inspect pull requests simultaneously across security, code quality, test coverage, and documentation.
- **Repository context retrieval.** Evaluates diffs alongside architecture records, existing utilities, and previous review comments using vector search.
- **Deduplication and scoring.** Merges overlapping findings, deduplicates repeated critiques, and scores confidence before posting comments.
- **Human approval queue.** Routes lower-confidence observations to a triage dashboard for engineering lead determination.
- **Token accounting and limits.** Tracks token spend per review, enforces daily budget quotas, and isolates external provider failures with circuit breakers.
- **Production container topology.** Fully decoupled multi-stage Docker containers with non-root service execution and automated health monitoring.
- **Mobile-friendly dashboard.** Next.js 15 web dashboard built on Apple Design principles with zero horizontal screen overflow.

---

## System architecture

Hadron uses an event-driven modular architecture with isolated boundaries between ingress, orchestration, execution, and presentation.

```mermaid
flowchart TD
    subgraph GitHub ["GitHub Platform"]
        PR["Pull Request Created / Synchronized"]
        Comment["Inline PR Comments & Review Summary"]
    end

    subgraph Ingress ["API & Ingress Gateway"]
        Webhook["FastAPI Ingress (/webhook/github)"]
        HMAC["HMAC SHA-256 Signature Verification"]
        Idempotency["Redis Idempotency & Replay Filter"]
    end

    subgraph Memory ["Vector Memory & Context Layer"]
        Chunks[("Repository Code Chunks")]
        Embedder["Embedding Engine"]
        VectorDB[("PostgreSQL + pgvector")]
    end

    subgraph Orchestration ["LangGraph Orchestration Core"]
        ContextNode["BuildContext Node"]
        
        subgraph Agents ["Parallel Specialist Swarm"]
            SecAgent["Security Specialist\n(OWASP, Secrets, Injection)"]
            QualAgent["Quality Specialist\n(Complexity, Smells, Design)"]
            TestAgent["Test Specialist\n(Assertions, Coverage, Regressions)"]
            DocAgent["Documentation Specialist\n(APIs, Specs, Breaking Changes)"]
        end

        AggregateNode["AggregateResults Node\n(Deduplication & Confidence Ranking)"]
        RouterNode{"Confidence >= Threshold?"}
    end

    subgraph Delivery ["Review Dispatch & Governance"]
        HITLQueue["Human-in-the-Loop Approval Queue"]
        PostNode["PostReview Node\n(GitHub REST API Client)"]
        EventsDB[("Agent Events & Observability")]
    end

    PR -->|Webhook POST| Webhook
    Webhook --> HMAC --> Idempotency
    Idempotency --> ContextNode
    
    ContextNode <-->|Semantic Search & Retrieval| VectorDB
    Embedder -.-> Chunks
    
    ContextNode --> SecAgent & QualAgent & TestAgent & DocAgent
    SecAgent & QualAgent & TestAgent & DocAgent --> AggregateNode
    
    AggregateNode --> RouterNode
    RouterNode -->|High Confidence| PostNode
    RouterNode -->|Low Confidence / Disputed| HITLQueue
    HITLQueue -->|Approved by Reviewer| PostNode
    
    PostNode --> Comment
    AggregateNode -.-> EventsDB
```

---

## Specialist agents

Each specialist operates under a strict role contract, using domain-specific prompts and contextual retrieval:

| Specialist | Domain Focus | Primary Checks & Heuristics |
| :--- | :--- | :--- |
| **Security** | Vulnerability prevention and data security | OWASP Top 10 vulnerabilities, CWE anti-patterns, exposed secrets and API keys, SQL injection, SSRF, XSS, insecure deserialization, authorization bypasses. |
| **Code Quality** | Maintainability, architecture, and performance | SOLID violations, cyclomatic complexity spikes, memory leaks, concurrency hazards, dead code, architectural pattern deviations. |
| **Test Coverage** | Regression prevention and test quality | Missing boundary test cases, brittle mock assertions, untested error branches, regression risks in modified business logic. |
| **Documentation** | Knowledge retention and spec accuracy | Missing or outdated docstrings, OpenAPI drift, misleading comments, undocumented public API breaking changes. |

---

## Workflow

1. **Ingress and verification:**
   - GitHub triggers an event payload when a PR opens or updates.
   - The ingress endpoint verifies the `X-Hub-Signature-256` payload against the GitHub App webhook secret.
   - Idempotency guards in Redis ensure duplicate delivery IDs are processed exactly once.

2. **Context and semantic retrieval:**
   - The orchestrator parses the unified diff and changed file paths.
   - Related files, historical reviews, and repository guidelines are retrieved from the vector store using embeddings.

3. **Parallel multi-agent execution:**
   - LangGraph runs all four specialist agents simultaneously.
   - Each agent produces structured JSON findings with category, severity, confidence, file, line, rationale, and suggested patch.

4. **Aggregation and scoring:**
   - Overlapping critiques across agents are merged and prioritized.
   - Findings receive severity tags: `CRITICAL`, `MAJOR`, `MINOR`, or `INFO`.
   - Each finding receives a confidence score between `0.0` and `1.0`.

5. **Decision and dispatch:**
   - Findings meeting the confidence threshold (`0.70` default) compile into a formatted Markdown GitHub review with inline diff comments.
   - Lower-confidence items route to the **human approval queue** for manual triage.

---

## Tech stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Web Dashboard** | **Next.js 15**, React, TailwindCSS | Dashboard for review history, approvals triage, and token economics |
| **Backend Core** | **FastAPI**, Python 3.11+, Uvicorn | Asynchronous REST and webhook API engine |
| **Agent Orchestration** | **LangGraph**, LangChain Core | Workflow graphs, checkpointing, and parallel fan-out |
| **Relational & Vector DB** | **PostgreSQL** + **pgvector** | Relational schema and embedding storage for RAG context |
| **Queue & Memory** | **Redis** | High-throughput distributed caching, state locking, and idempotency |
| **Worker Engine** | **ARQ**, AsyncIO | Decoupled background queue worker processing review tasks |
| **Containerization** | **Docker**, Docker Compose | Multi-stage, unprivileged non-root execution topology |
| **LLM & Reasoning** | **OpenAI GPT-4o** / Anthropic Claude | Reasoning models selected dynamically per agent domain |
| **Observability** | **OpenTelemetry**, Structured Logging | Token attribution, distributed traces, and automated circuit breakers |

---

## Repository structure

```text
Hadron/
├── api/                      Vercel ASGI adapter
├── backend/                  Python domain packages and ARQ worker
├── frontend/
│   ├── src/app/              Next.js routes and layouts
│   ├── src/features/         Auth, reviews, HITL, overview, marketing
│   ├── src/components/       Shared ui, brand, and layout components
│   ├── src/lib/              API transport, DTOs, theme and SWR
│   ├── tests/                Browser regression checks
│   ├── Dockerfile            Multi-stage standalone Next.js container
│   └── public/               Browser-served assets
├── tests/                    Python tests grouped by domain
├── fixtures/                 Shared demo/test webhook payload
├── scripts/                  Operational tools and migration artifacts
├── docs/                     Architecture, operations, design and evidence
├── assets/                   Repository branding assets
├── Dockerfile                Multi-stage backend container (API & Worker)
├── docker-compose.yml        Production compose topology
├── docker-compose.dev.yml    All-local development compose topology
└── .github/workflows/        CI and production readiness gate
```

See [repository layout](docs/architecture/repository-layout.md) for dependency rules, verified upstream examples, and the exact move mapping. The [documentation index](docs/README.md) and [test guide](tests/README.md) provide focused entrypoints.

---

## Containerization & Docker architecture

Hadron implements an enterprise multi-stage container strategy designed around clean process decoupling, minimal surface area, and unprivileged execution.

### Container topology

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DOCKER COMPOSE TOPOLOGY                         │
├──────────────┬──────────────────┬──────────────┬───────────────────────┤
│ Service      │ Base Image       │ Port         │ Responsibilities      │
├──────────────┼──────────────────┼──────────────┼───────────────────────┤
│ frontend     │ node:20-alpine   │ 3000:3000    │ Next.js 15 Standalone │
│ api          │ python:3.11-slim │ 8000:8000    │ FastAPI & Webhooks    │
│ worker       │ python:3.11-slim │ (Internal)   │ ARQ Review Pipeline   │
│ redis        │ redis:7.2-alpine │ 6379:6379    │ AOF Idempotency Queue │
│ postgres*    │ postgres:16      │ 5433:5432    │ Relational + pgvector │
└──────────────┴──────────────────┴──────────────┴───────────────────────┘
* Included in local development topology (docker-compose.dev.yml).
```

### Multi-stage build design

- **Root `Dockerfile` (Backend & Worker):**
  - **Stage 1 (`builder`):** Compiles native C dependencies (`build-essential`, `libpq-dev`), leverages `uv` for fast package resolution, and pre-compiles wheels.
  - **Stage 2 (`runtime`):** Minimal `python:3.11-slim` image containing only `libpq5` runtime libraries. Creates an unprivileged system user (`hadron`, UID 1000). The entrypoint (`/app/scripts/entrypoint.sh`) dynamically executes either `api`, `worker`, or `combined` commands without privilege escalation.
  - **Healthcheck:** Probes `/health/live` with 30s intervals and 5s timeout.
- **Frontend `Dockerfile`:**
  - **Stage 1 (`deps`):** Caches `node_modules` via `npm ci`.
  - **Stage 2 (`builder`):** Compiles Next.js with `output: "standalone"`, extracting static assets and minified server bundles.
  - **Stage 3 (`runner`):** Minimal Alpine image running as non-root user `nextjs` (UID 1001).
  - **Healthcheck:** Probes `http://localhost:3000/` with wget.

---

## Getting started

### Prerequisites

- **Docker** & **Docker Compose** (recommended for quickstart)
- Or for bare-metal local development:
  - **Python 3.11+** with `uv`
  - **Node.js 20+** with `npm`
  - **PostgreSQL 15+** with the `vector` extension
  - **Redis 7+**

---

### 1. Environment configuration

Clone the repository and prepare your environment file:

```bash
git clone https://github.com/krishujeniya/Hadron.git
cd Hadron
cp .env.example .env
```

Edit `.env` with your credentials:

```ini
# Application Environment
APP_ENV=development
LOG_LEVEL=INFO

# Database Connection (PostgreSQL with pgvector)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/pr_review_agent

# Redis Queue Connection
REDIS_URL=redis://localhost:6379

# LLM Providers (OpenAI or Anthropic)
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key

# GitHub App Configuration
GITHUB_TOKEN=your-github-token
GITHUB_WEBHOOK_SECRET=your-webhook-secret
```

---

### 2. Running with Docker Compose

#### Option A: All-Local Development Mode (Recommended)
Spins up a self-contained local stack including PostgreSQL (on host port 5433 with pgvector), Redis (port 6379), FastAPI backend (port 8000), ARQ review worker, and the Next.js frontend (port 3000):

```bash
# Build and launch all services in background
docker compose -f docker-compose.dev.yml up -d --build

# Verify running services and health status
docker compose -f docker-compose.dev.yml ps

# Follow logs from API and background worker
docker compose -f docker-compose.dev.yml logs -f api worker
```

#### Option B: Production Compose Topology
Spins up the production frontend, API, decoupled ARQ worker fleet, and persistent Redis, connecting to your managed PostgreSQL database (e.g., Supabase or Neon):

```bash
# Build and launch production containers
docker compose up -d --build

# Inspect container health
docker compose ps
```

#### Container Management Commands

```bash
# View aggregated service logs
docker compose logs -f

# Run database migrations inside the API container
docker compose exec api python3 scripts/migrate.py

# Open an interactive shell inside the backend container
docker compose exec api bash

# Scale review worker processes
docker compose up -d --scale worker=3

# Gracefully stop all containers
docker compose down

# Stop containers and purge local data volumes
docker compose down -v
```

---

### 3. Running Locally (Bare Metal)

If you prefer to run services directly on your host machine:

#### Backend Setup
```bash
# Create and sync Python virtual environment with uv
uv sync

# Or install with pip
pip install -r requirements.txt

# Start the FastAPI API server
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# In a separate terminal, start the ARQ worker
uv run python -m arq backend.job_queue.arq_worker.WorkerSettings
```

#### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

- **Backend API:** `http://localhost:8000`
- **Interactive OpenAPI Documentation:** `http://localhost:8000/docs`
- **Frontend Dashboard:** `http://localhost:3000`

---

## Running tests and verification

The repository enforces automated verification across all layers:

```bash
# 1. Verify structure and import boundaries
python3 scripts/check_structure.py

# 2. Python linting and formatting check
uv run ruff check .

# 3. Frontend static typecheck
npm --prefix frontend run lint

# 4. Next.js production build verification
npm --prefix frontend run build

# 5. Full deterministic Python test suite (414 tests)
uv run pytest tests/ -m "not eval"

# 6. Playwright browser UI regression checks
npm run test:ui --prefix frontend
```

---

## Health checks and monitoring

Each service exposes dedicated healthcheck endpoints:

| Endpoint | Target Component | Purpose |
| :--- | :--- | :--- |
| `GET /health/live` | API Server | Minimal liveness probe (0 external dependencies) |
| `GET /health/ready` | API & Dependencies | Validates Postgres connection, schema DDL, Redis, and worker heartbeat |
| `GET /api/v1/economics/budget` | Budget Guard | Real-time daily token expenditure and hard ceiling status |
| `GET /` | Frontend Dashboard | Web interface availability probe |

---

## Security, privacy and governance

- **Zero source code retention.** Pull request diffs are processed in-memory during workflow execution and never retained for model training.
- **Cryptographic HMAC verification.** Webhooks require valid `X-Hub-Signature-256` signatures matching `GITHUB_WEBHOOK_SECRET`.
- **Unprivileged container isolation.** Production Docker containers run as non-root service accounts (`hadron` UID 1000, `nextjs` UID 1001).
- **Strict secret redaction.** Sensitive tokens, private keys, and passwords in diffs are masked before agent evaluation.
- **Circuit breakers.** Failures in external LLM APIs isolate gracefully to prevent cascading timeouts.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

<p align="center">
  Crafted by <strong><a href="https://github.com/krishujeniya">Krish Ujeniya</a></strong>
</p>
