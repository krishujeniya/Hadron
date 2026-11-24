# Hadron Setup & Local Development Guide

## Prerequisites

- Python 3.11+
- Node.js 20+
- `uv` package manager
- Docker & Docker Compose (optional for local services)

## Quickstart

### 1. Backend

```bash
cd backend
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
uvicorn main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. Unified Make Commands

From the repository root:
```bash
make dev     # Run development services
make test    # Run test suite
make build   # Build frontend and backend artifacts
```
