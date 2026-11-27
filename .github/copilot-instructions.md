# Copilot & Agent Instructions for Hadron

- Maintain `main` as the sole permanent branch.
- Author commits as `Krish Ujeniya <100012208+krishujeniya@users.noreply.github.com>`.
- Execute all Python tasks exclusively via `uv` (`uv run ...`, `uv sync ...`).
- Never commit secrets, `.env` files, or agent workspace metadata (`GEMINI.md`, `CLAUDE.md`, `.cursor/`, etc.).
- Keep Dockerfiles and compose files inside `deploy/docker/` for local parity; deploy edge worker/frontend via `.github/workflows/deploy.yml`.
