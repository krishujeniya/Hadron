# Python tests

Tests are grouped by behavior: `agents`, `api`, `data`, `documentation`, `economics`, `evaluation`, `frontend`, `operations`, `reliability`, `security`, and `workflows`. Select a directory to work on one area. File names describe the behavior being tested instead of a development phase or tracker ticket.

Run from the repository root with the development environment installed:

```bash
.venv/bin/python -m pytest tests/ -q -m 'not eval'
.venv/bin/python -m pytest tests/security/ -q
python3 scripts/check_structure.py
```

Use isolated service configuration and placeholder credentials. The verified local run supplied `APP_ENV=test`, `DATABASE_URL=sqlite+aiosqlite:///:memory:`, `REDIS_URL=redis://127.0.0.1:1`, `QDRANT_URL=http://127.0.0.1:1`, an empty `TIGER_DATABASE_URL`, and placeholder GitHub/OpenAI/Anthropic/API keys. CI defines its own test environment. Do not point these tests at production resources.

`tests/evaluation/test_eval_gate.py` is the paid provider test, marked `eval`. It is excluded from the deterministic command above. Other evaluation tests use mocked provider responses. Test directory names do not imply that external services are contacted.

`tests/frontend` contains the existing Python source-contract checks. Runtime browser regressions are in `frontend/tests/check-ui.mjs` and run with `npm run test:ui --prefix frontend` against a locally built frontend server. They use mocked API responses and do not validate real GitHub authorization.

Pytest adds the repository root to Python's import path using `pyproject.toml`. The complete move mapping is in `docs/verification/structure-moves-2026-11-02.json`.
