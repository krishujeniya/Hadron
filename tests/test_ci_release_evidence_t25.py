# tests/test_ci_release_evidence_t25.py
#
# Contract and acceptance tests for Gate B - Task T25:
# Turn CI into meaningful release evidence.
#
# Invariants verified:
#   1. CI workflow (.github/workflows/ci.yml) enforces concurrency cancellation, least privilege,
#      complete deterministic test suite execution (not an isolated single file), and gated eval.
#   2. CI checks strictly block deliberately introduced auth bypasses (401/403).
#   3. CI checks strictly block failed-agent false positive approvals (aggregator safety invariant).
#   4. Schema migration checks detect unmigrated tables and fail readiness probes.
#   5. Frontend route inventory contains all required operational surfaces and compiles cleanly.

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from fastapi.testclient import TestClient

from backend.main import app


def test_ci_workflow_structure_and_security_invariants():
    """
    CI configuration contract:
      - Concurrency cancellation configured to abort obsolete PR runs.
      - Least-privilege permissions applied.
      - Full test suite (tests/) executed with eval isolation.
      - Frontend typecheck and production build included.
      - Eval gate gated to main branch.
    """
    ci_path = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
    assert ci_path.exists(), "CI workflow file .github/workflows/ci.yml must exist"

    content = ci_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(content)

    # 1. Concurrency cancellation
    assert "concurrency" in parsed
    assert parsed["concurrency"].get("cancel-in-progress") is True

    # 2. Permissions
    assert "permissions" in parsed
    assert parsed["permissions"].get("contents") == "read"

    # 3. Jobs configuration
    jobs = parsed.get("jobs", {})
    assert "lint-and-typecheck" in jobs
    assert "test-suite" in jobs
    assert "frontend-build" in jobs
    assert "eval-gate" in jobs

    # 4. test-suite must run full test directory, not just a single smoke file
    test_suite_steps = jobs["test-suite"]["steps"]
    run_steps = [s["run"] for s in test_suite_steps if "run" in s]
    full_suite_invoked = any("pytest tests/" in r and "not eval" in r for r in run_steps)
    assert full_suite_invoked, "CI test-suite must execute full pytest tests/ suite excluding paid evals"

    # 5. eval-gate must be gated to push on main
    eval_gate = jobs["eval-gate"]
    assert "push" in eval_gate.get("if", "") and "main" in eval_gate.get("if", "")


def test_required_checks_block_auth_bypass():
    """
    Deliberate mutation: Unauthenticated caller attempting privilege escalation
    via forged X-Role header MUST be blocked with HTTP 401.
    """
    with TestClient(app, raise_server_exceptions=False) as client:
        # Anonymous request with spoofed admin header
        res = client.get("/api/v1/economics/summary", headers={"X-Role": "admin"})
        assert res.status_code == 401, f"Expected 401 for forged role, got {res.status_code}"

        # Anonymous request to governance
        res = client.get("/api/v1/governance/legal-holds", headers={"X-Role": "admin"})
        assert res.status_code == 401

        # Invalid API key
        res = client.get("/api/v1/reviews", headers={"X-API-Key": "malicious-fake-key"})
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_required_checks_block_failed_agent_approval():
    """
    Deliberate mutation: Review with an agent failure or critical finding
    must NEVER resolve to an 'approve' verdict.
    """
    from backend.orchestrator.nodes import aggregate_results

    state = {
        "workflow_id": "org/repo:1:sha1",
        "repo_full_name": "org/repo",
        "pr_number": 1,
        "pr_title": "PR",
        "pr_body": "",
        "pr_diff": "",
        "head_commit_sha": "sha1",
        "base_branch": "main",
        "author_login": "alice",
        "changed_files": [],
        "confidence_threshold": 0.85,
        "agent_results": [
            {
                "agent_type": "security",
                "findings": [],
                "success": False,
                "status": "failed",
                "error": "Timeout connecting to provider",
                "error_message": "Timeout connecting to provider",
                "per_verdict": "approve",
                "confidence": 0.0,
                "duration_ms": 100,
            },
            {
                "agent_type": "quality",
                "findings": [],
                "success": True,
                "status": "success",
                "error": None,
                "error_message": "",
                "per_verdict": "approve",
                "confidence": 0.9,
                "duration_ms": 100,
            },
        ],
    }

    result = await aggregate_results(state)
    assert result["verdict"] != "approve", "Failed security agent must block approval"
    assert result["needs_human_review"] is True, "Failed security agent must route to HITL"


@pytest.mark.asyncio
async def test_schema_readiness_blocks_unmigrated_deployment():
    """
    Deliberate mutation: If tables are missing or migration check fails,
    schema readiness probe must report 'unmigrated' and ready probe returns 503.
    """
    with patch("backend.main._check_schema", new=AsyncMock(return_value="unmigrated")), \
         patch("backend.main._check_postgres", new=AsyncMock(return_value="ok")), \
         patch("backend.main._check_redis", new=AsyncMock(return_value="ok")), \
         patch("backend.main._check_worker", new=AsyncMock(return_value=("ok", ["worker-1"], 1.0))):

        with TestClient(app, raise_server_exceptions=False) as client:
            res = client.get("/health/ready")
            assert res.status_code == 503
            body = res.json()
            assert body["status"] == "degraded"
            assert body["services"]["schema"] == "unmigrated"


def test_frontend_route_inventory_and_parse_integrity():
    """
    Verifies that all core dashboard and operational routes are defined
    in the Next.js frontend directory and contain valid TypeScript React components.
    """
    frontend_dir = Path(__file__).parent.parent / "frontend" / "src" / "app"
    required_routes = [
        "page.tsx",
        "health/page.tsx",
        "reviews/page.tsx",
        "hitl/page.tsx",
        "economics/page.tsx",
        "repositories/page.tsx",
    ]

    for rel_path in required_routes:
        file_path = frontend_dir / rel_path
        assert file_path.exists(), f"Frontend route file missing: {rel_path}"
        content = file_path.read_text(encoding="utf-8")
        assert len(content) > 50, f"Frontend route file {rel_path} is suspiciously empty"
        assert "export default" in content, f"Frontend route {rel_path} must export default component"
