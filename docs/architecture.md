# Hadron Architecture Documentation

Hadron is an autonomous, multi-agent GitHub Pull Request review platform designed for enterprise codebases.

## Monorepo Layout

- **`frontend/`**: Next.js App Router application providing the real-time review dashboard and human-in-the-loop (HITL) interface.
- **`backend/`**: FastAPI application handling review orchestration, multi-agent evaluations, webhooks, and security checks.
- **`deploy/`**: Container configurations (`deploy/docker/`), compose files (`docker-compose.yml`, `docker-compose.dev.yml`), and hosting/Cloudflare configs.
- **`docs/`**: Architecture, setup, runbooks, security records, and ADRs.
- **`scripts/`**: Automation scripts, DB migration tools, and sanity checks.
- **`assets/`**: Brand assets, favicons, logos, and diagrams.
