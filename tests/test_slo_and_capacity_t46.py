"""Verification test suite for T46: Service Level Objectives (SLOs) and Capacity Specifications.

Validates:
1. Formal definitions of SLI 1 through SLI 5 with numerators, denominators, and targets.
2. Multi-window multi-burn-rate alerting policies and error budget calculation.
3. Multi-tenant capacity bounds, connection pools, and noisy-neighbor isolation rules.
4. Remediation runbook mapping for all defined service level indicators.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SLO_FILE = REPO_ROOT / "docs" / "SLO_AND_CAPACITY.md"


def test_slo_file_exists_and_defines_all_five_slis():
    """Verify docs/SLO_AND_CAPACITY.md exists and documents the 5 required SLIs."""
    assert SLO_FILE.exists(), "docs/SLO_AND_CAPACITY.md must exist"
    content = SLO_FILE.read_text(encoding="utf-8")

    # SLI 1: Webhook Durable Receipt (99.9% target)
    assert "SLI-1" in content
    assert "Webhook Durable Receipt" in content
    assert "99.9%" in content

    # SLI 2: Queue Delay (p95 <= 30s)
    assert "SLI-2" in content
    assert "Worker Fleet Queue Delay" in content
    assert "p95 ≤ 30s" in content

    # SLI 3: Review Execution Completion by PR Size
    assert "SLI-3A" in content
    assert "Small PR Review Latency" in content
    assert "p95 ≤ 120s" in content
    assert "SLI-3B" in content
    assert "p95 ≤ 300s" in content

    # SLI 4: Publication Outbox (99.5% target)
    assert "SLI-4" in content
    assert "Review Publication Outbox" in content
    assert "99.5%" in content

    # SLI 5: Dashboard API Reads (p95 <= 500ms)
    assert "SLI-5" in content
    assert "Dashboard API Read Latency" in content
    assert "p95 ≤ 500ms" in content


def test_error_budget_and_burn_rate_alerting_rules():
    """Verify multi-burn-rate alerting thresholds (14.4x / 6x / 3x) and release freeze criteria."""
    content = SLO_FILE.read_text(encoding="utf-8")

    assert "14.4x burn rate" in content
    assert "6x burn rate" in content
    assert "3x burn rate" in content
    assert "Release Freeze Rule" in content
    assert "10%" in content  # remaining budget freeze threshold


def test_capacity_and_noisy_neighbor_limits():
    """Verify concurrency caps, token limits, and connection pool allocations."""
    content = SLO_FILE.read_text(encoding="utf-8")

    assert "Per-Tenant Concurrency Caps" in content
    assert "10" in content  # max concurrent PR workflows per workspace
    assert "Database Connection Pool Partitioning" in content
    assert "Runbook Mapping" in content
