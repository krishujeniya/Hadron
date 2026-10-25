<p align="center">
  <img src="assets/logo.png" alt="Hadron — Autonomous AI PR Review Engine" width="540" />
</p>

# Hadron — Autonomous Multi-Agent PR Review Engine

<p align="center">
  <a href="https://hadron.vercel.app"><img src="https://img.shields.io/badge/Live_Dashboard-hadron.vercel.app-000000?style=for-the-badge&logo=vercel&logoColor=white" alt="Live Dashboard" /></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Next.js-14-000000?style=for-the-badge&logo=nextdotjs&logoColor=white" alt="Next.js 14" />
  <img src="https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/LangGraph-Stateful_Orchestration-1C3C3C?style=for-the-badge" alt="LangGraph" />
  <img src="https://img.shields.io/badge/PostgreSQL-pgvector-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL pgvector" />
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License" />
</p>

> **Hadron** is an enterprise-grade, autonomous AI code review platform. When a pull request opens on GitHub, Hadron fans out specialized multi-agent reviewers in parallel, retrieves deep codebase context via semantic vector search (RAG), synthesizes findings with calibrated confidence scoring, and posts high-signal, actionable feedback directly to the PR diff — routing borderline observations to a human-in-the-loop triage interface.

---

## 🌟 Key Highlights

- **⚡ Multi-Agent Parallel Fan-Out:** Four autonomous specialist agents review the PR simultaneously across Security, Code Quality, Test Coverage, and Documentation.
- **🧠 Semantic Context Engine (RAG):** Evaluates incoming diffs not in isolation, but against repository-wide architecture, ADRs, existing utility patterns, and previous PR reviews.
- **🎯 Deterministic Synthesis & Aggregation:** Consolidates multi-agent findings, deduplicates overlapping critique, scores confidence, and filters out noise before reaching the developer.
- **🛡️ Human-in-the-Loop (HITL) Safety Gate:** Borderline and lower-confidence observations are automatically queued in an interactive web portal for engineering lead triage.
- **📊 Real-Time Observability & Economics:** Complete token accounting, latency metrics, audit trail, and circuit breakers designed for high-throughput enterprise scale.
- **💻 Full-Stack Architecture:** Modular FastAPI backend orchestrating state machines alongside a Next.js 14 web app for live reviews and analytics.

---

## 🏗️ System Architecture

Hadron operates as a resilient, event-driven modular architecture with deterministic boundaries between ingestion, orchestration, execution, and presentation.

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

## 🤖 The Specialist Agent Swarm

Each specialist operates under a strict role contract, utilizing domain-specific prompt engineering and contextual retrieval:

| Specialist | Domain Focus | Primary Checks & Heuristics |
| :--- | :--- | :--- |
| **🛡️ Security** | Vulnerability prevention & data security | OWASP Top 10 vulnerabilities, CWE anti-patterns, exposed secrets/API keys, SQLi, SSRF, XSS, insecure deserialization, authorization bypasses. |
| **⚡ Code Quality** | Maintainability, architecture & performance | SOLID violations, cyclomatic complexity spikes, memory leaks, concurrency hazards, dead code, architectural pattern deviations. |
| **🧪 Test Coverage** | Regression prevention & verification | Missing boundary test cases, brittle mock assertions, untested error branches, regression risks in modified business logic. |
| **📚 Documentation** | Knowledge retention & clarity | Missing or outdated docstrings, OpenAPI/Swagger drift, misleading comments, undocumented public API breaking changes. |

---

## 🔄 End-to-End Workflow

1. **Ingress & Authentication:**
   - GitHub triggers an event payload when a PR is opened or updated.
   - The ingress endpoint validates the `X-Hub-Signature-256` payload against the GitHub App webhook secret.
   - Idempotency guards in Redis ensure duplicate delivery IDs are processed exactly once.

2. **Context & Semantic Enrichment:**
   - The orchestrator parses the unified diff and changed file paths.
   - Related files, historical reviews, and repository guidelines are retrieved from the vector store via cosine similarity embeddings.

3. **Parallel Multi-Agent Reasoning:**
   - LangGraph fans out execution across all four specialist agents simultaneously.
   - Each agent produces structured JSON findings adhering to a unified schema (`category`, `severity`, `confidence`, `file`, `line`, `rationale`, `suggested_patch`).

4. **Aggregation & Normalization:**
   - Overlapping critiques across agents are coalesced and prioritized.
   - Severity tags are assigned: `CRITICAL`, `MAJOR`, `MINOR`, or `INFO`.
   - Each finding is assigned an empirical confidence score between `0.0` and `1.0`.

5. **Decision & Dispatch:**
   - Findings meeting or exceeding the confidence threshold (`0.70` default) are compiled into a formatted Markdown GitHub review with inline diff comments.
   - Lower-confidence items are diverted to the **HITL (Human-in-the-Loop) Queue** to eliminate false-positive noise and prevent reviewer fatigue.

---

## 💻 Tech Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Web Dashboard** | **Next.js 14**, React, TailwindCSS, Lucide | Modern dashboard for monitoring review runs, triage queue, and cost analytics |
| **Backend Core** | **FastAPI**, Python 3.10+, Uvicorn | High-performance asynchronous API engine |
| **Agent Orchestration** | **LangGraph**, LangChain Core | Stateful workflow graphs, checkpointing, and parallel fan-out |
| **Relational & Vector DB** | **PostgreSQL** + **pgvector** | Unified relational schema and embedding storage for RAG context |
| **Queue & Memory** | **Redis** | High-throughput distributed caching, state locking, and idempotency |
| **LLM & Reasoning** | **OpenAI GPT-4o** / Anthropic Claude | Reasoning models selected dynamically per agent domain |
| **Observability** | **OpenTelemetry**, Structured Logging | Token attribution, distributed traces, and automated circuit breakers |

---

## 📁 Repository Structure

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
├── frontend/                  # Next.js 14 dashboard & review portal
│   ├── src/app/               # App Router pages (reviews, queue, analytics)
│   ├── src/components/        # Reusable UI components & metrics graphs
│   └── src/lib/               # Client-side API bindings & state handlers
├── docs/                      # Architecture Decision Records (ADRs) & documentation
├── scripts/                   # Migration helpers and execution entrypoints
├── tests/                     # Unit, integration, and orchestration test suites
└── docker-compose.yml         # Container configuration for local development
```

---

## 🚀 Getting Started

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

## 🧪 Running Tests

The test suite validates agent contracts, state orchestration, idempotency, and regression gates:

```bash
# Run full test suite
pytest -v

# Run targeted orchestration tests
pytest tests/test_phase13.py -v
```

---

## 🛡️ Security & Privacy Guardrails

- **Zero Source Retention:** Source code and pull request diffs are processed in-memory during workflow execution and never retained for foundation model training.
- **HMAC Verification:** Every incoming webhook is cryptographically verified against the secret signature before execution triggers.
- **Circuit Breaker Protection:** Integrated fail-safes isolate external provider disruptions, ensuring high availability and predictable degradation.
- **Granular RBAC:** Complete role-based access control governing the HITL approval interface and repository configurations.

---

## 📄 License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).

---

<p align="center">
  Crafted with precision by <strong><a href="https://github.com/krishujeniya">Krish Ujeniya</a></strong>
</p>
