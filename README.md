<p align="center">
  <img src="assets/logo.png" alt="Hadron AI PR review engine" width="540" />
</p>

# Hadron: autonomous multi-agent PR review engine

<p align="center">
  <a href="https://hadron.vercel.app"><img src="https://img.shields.io/badge/Live_Dashboard-hadron.vercel.app-000000?style=for-the-badge&logo=vercel&logoColor=white" alt="Live Dashboard" /></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/Next.js-15-000000?style=for-the-badge&logo=nextdotjs&logoColor=white" alt="Next.js 15" />
  <img src="https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/LangGraph-Stateful_Orchestration-1C3C3C?style=for-the-badge" alt="LangGraph" />
  <img src="https://img.shields.io/badge/PostgreSQL-pgvector-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL pgvector" />
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License" />
</p>

> Hadron reviews pull requests with four specialist sub-agents running in parallel: security, code quality, test coverage, and documentation. It fetches relevant repository context with vector search, scores finding confidence, and posts inline review comments to the pull request. Borderline findings are routed to a human approval queue.

---

## Key features

- **Multi-agent parallel review.** Four autonomous specialist agents inspect pull requests simultaneously across security, code quality, test coverage, and documentation.
- **Repository context retrieval.** Evaluates diffs alongside architecture records, existing utilities, and previous review comments using vector search.
- **Deduplication and scoring.** Merges overlapping findings, deduplicates repeated critiques, and scores confidence before posting comments.
- **Human approval queue.** Routes lower-confidence observations to a triage dashboard for engineering lead review.
- **Token accounting and limits.** Tracks token spend per review, enforces daily budget quotas, and isolates external provider failures with circuit breakers.
- **Full-stack architecture.** FastAPI backend with LangGraph state machines and a Next.js 15 web dashboard.

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
            SecAgent["🛡️ Security Specialist\n(OWASP, Secrets, Injection)"]
            QualAgent["⚡ Quality Specialist\n(Complexity, Smells, Design)"]
            TestAgent["🧪 Test Specialist\n(Assertions, Coverage, Regressions)"]
            DocAgent["📚 Documentation Specialist\n(APIs, Specs, Breaking Changes)"]
        end

        AggregateNode["AggregateResults Node\n(Deduplication & Confidence Ranking)"]
        RouterNode{"Confidence >= Threshold?"}
    end

    subgraph Delivery ["Review Dispatch & Governance"]
        HITLQueue["👤 Human-in-the-Loop Approval Queue"]
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
| **Web Dashboard** | **Next.js 15**, React, TailwindCSS, Lucide | Dashboard for review history, approvals triage, and token economics |
| **Backend Core** | **FastAPI**, Python 3.11+, Uvicorn | Asynchronous REST and webhook API engine |
| **Agent Orchestration** | **LangGraph**, LangChain Core | Workflow graphs, checkpointing, and parallel fan-out |
| **Relational & Vector DB** | **PostgreSQL** + **pgvector** | Relational schema and embedding storage for RAG context |
| **Queue & Memory** | **Redis** | High-throughput distributed caching, state locking, and idempotency |
| **LLM & Reasoning** | **OpenAI GPT-4o** / Anthropic Claude | Reasoning models selected dynamically per agent domain |
| **Observability** | **OpenTelemetry**, Structured Logging | Token attribution, distributed traces, and automated circuit breakers |

---

## Repository structure

```
Hadron/
├── assets/                    # Project logos, icons, and branding assets
├── backend/
│   ├── agents/                # Specialist agent implementations & contracts
│   │   ├── base_agent.py      # Abstract agent interface & execution harness
│   │   ├── security_agent.py  # Security vulnerability specialist
│   │   ├── quality_agent.py   # Code cleanliness & architecture specialist
│   │   ├── test_agent.py      # Test coverage & regression specialist
│   │   └── docs_agent.py      # Documentation & API contract specialist
│   ├── api/                   # REST routing (webhooks, reviews, HITL, stats)
│   ├── auth/                  # Authentication dependencies & session handling
│   ├── config/                # App configuration, settings & environment models
│   ├── database/              # PostgreSQL async models, migrations & repositories
│   ├── economics/             # Token budget controls & cost attribution ledger
│   ├── evaluation/            # Automated evaluation gates & LLM-as-judge suite
│   ├── hitl/                  # Human-in-the-Loop review queue & escalation logic
│   ├── integrations/          # GitHub API client & webhook payload models
│   ├── memory/                # Vector store, context retriever & embeddings
│   ├── observability/         # OpenTelemetry tracing, audit logs & metrics
│   ├── orchestrator/          # LangGraph graph topology, state models & nodes
│   ├── prompts/               # System prompt registry & agent templates
│   ├── reliability/           # Circuit breakers, retries & idempotency filters
│   ├── tools/                 # Tool registry & model routing utilities
│   └── webhook_receiver/      # GitHub webhook signature validator & parser
├── frontend/                  # Next.js 15 dashboard & review portal
│   ├── src/app/               # App Router pages (reviews, queue, analytics)
│   ├── src/components/        # Reusable UI components & metrics graphs
│   └── src/lib/               # Client-side API bindings & state handlers
├── docs/                      # Architecture Decision Records (ADRs) & documentation
├── scripts/                   # Migration helpers and execution entrypoints
├── tests/                     # Unit, integration, and orchestration test suites
└── docker-compose.yml         # Container configuration for local development
```

---

## Getting started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** & npm / pnpm
- **PostgreSQL 15+** with the `vector` extension enabled
- **Redis 6+**
- **GitHub App** (or Personal Access Token for testing)
- **OpenAI API Key**

---

### Local Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/krishujeniya/Hadron.git
   cd Hadron
   ```

2. **Configure Environment Variables:**
   ```bash
   cp .env.example .env
   ```
   Populate your `.env` file with your local credentials:
   ```ini
   # App Environment
   ENVIRONMENT=development
   LOG_LEVEL=INFO

   # Database (PostgreSQL with pgvector)
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/hadron_db

   # Redis
   REDIS_URL=redis://localhost:6379/0

   # LLM Providers
   OPENAI_API_KEY=your-openai-api-key

   # GitHub App Configuration
   GITHUB_APP_ID=your-github-app-id
   GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
   GITHUB_WEBHOOK_SECRET=your-webhook-secret
   ```

3. **Start with Docker Compose (Recommended):**
   ```bash
   docker compose up -d
   ```

4. **Or Run Locally:**

   **Backend:**
   ```bash
   # Install dependencies
   pip install -r requirements.txt

   # Start the FastAPI server
   uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```

   **Frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   - **Backend API:** `http://localhost:8000`
   - **Interactive API Docs:** `http://localhost:8000/docs`
   - **Frontend Dashboard:** `http://localhost:3000`

---

## Running tests

The test suite validates agent contracts, state orchestration, idempotency, and regression gates:

```bash
# Run full test suite
pytest -v

# Run targeted orchestration tests
pytest tests/test_phase13.py -v
```

---

## Security and privacy

- **Zero source retention.** Source code and pull request diffs are processed in-memory during workflow execution and never stored or retained for model training.
- **HMAC verification.** Every incoming webhook is cryptographically verified against the secret signature before execution triggers.
- **Circuit breaker protection.** Integrated fail-safes isolate external provider disruptions, ensuring high availability and predictable degradation.
- **Role-based access control.** Explicit role model governing the approval interface and repository configurations.

---

## License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).

---

<p align="center">
  Crafted by <strong><a href="https://github.com/krishujeniya">Krish Ujeniya</a></strong>
</p>
