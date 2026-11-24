# AGENTS.md — Global Operational Rules for Hadron

## 1. Git & GitHub Profile Invariants
- **Profile Identity**:
  - Name: `Krish Ujeniya`
  - Email: `100012208+krishujeniya@users.noreply.github.com`
  - Profile URL: `https://github.com/krishujeniya`
- **Rule**:
  - All commits must strictly be authored and committed under this identity to match the user's GitHub profile (`github.com/krishujeniya`).
  - When tasks/features are completed, stage, commit with conventional commit messages, and push directly to GitHub.

## 2. CI/CD & Testing Discipline
- **Rule**:
  - Do NOT run heavy tests, Docker container builds, or manual E2E test runs locally.
  - Rely on **GitHub Actions CI/CD** (`.github/workflows/ci.yml`, `cloudflare-deploy.yml`, etc.) for official build, lint, test execution, and deployment verification.
  - Maintain clean, minimal changes and verify through the remote GitHub Actions pipeline.

## 3. Production Deployment & Cloudflare Tech Stack
- **Rule**:
  - Production deployments must exclusively use the **Cloudflare tech stack** (Cloudflare Pages + Cloudflare Workers).
  - Use URL conventions:
    - **Frontend**: `<projectname>.pages.dev` (e.g. `hadron.pages.dev`)
    - **Backend**: `api.<projectname>.workers.dev` (e.g. `api.hadron.workers.dev` or `hadron.workers.dev` / `api-hadron-pr.pages.dev`)
  - All routing, proxies, and CORS allowlists must support and align with these Cloudflare production endpoints.
