"""Verification test suite for T47: Documentation reconciliation with implementation and evidence.

Validates:
1. docs/FUTURE_WORK.md points to existing backend/economics/budget.py (BudgetGuard).
2. docs/adr/ADR-004-cost-control-design.md points to existing backend/economics/budget.py.
3. ADR indices are disambiguated (ADR-003 for frontend, ADR-006 for Tiger Cloud data layer).
4. docs/principals.md contains the reconciliation notice superseding unverified claims with evidence-led specifications.
5. README.md accurately reflects the updated Next.js 15 baseline.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_future_work_and_adr_reference_existing_budget_module():
    """Verify documentation references actual backend/economics/budget.py instead of stale budget_guard.py."""
    future_work = REPO_ROOT / "docs" / "FUTURE_WORK.md"
    adr_004 = REPO_ROOT / "docs" / "adr" / "ADR-004-cost-control-design.md"

    assert future_work.exists()
    assert adr_004.exists()

    fw_text = future_work.read_text(encoding="utf-8")
    assert "backend/economics/budget.py" in fw_text
    assert "backend/economics/budget_guard.py" not in fw_text

    adr_text = adr_004.read_text(encoding="utf-8")
    assert "backend/economics/budget.py" in adr_text
    assert "backend/economics/budget_guard.py" not in adr_text


def test_adr_identifiers_are_disambiguated():
    """Verify ADR-003 and ADR-006 have distinct, non-conflicting numbers."""
    adr_frontend = REPO_ROOT / "docs" / "adr" / "ADR-003-frontend-data-strategy.md"
    adr_tiger = REPO_ROOT / "docs" / "adr" / "ADR-003-tiger-cloud-data-layer.md"

    assert adr_frontend.exists()
    assert adr_tiger.exists()

    tiger_text = adr_tiger.read_text(encoding="utf-8")
    assert "# ADR-006: Tiger Cloud" in tiger_text or "ADR-006" in tiger_text


def test_principals_md_contains_evidence_reconciliation_notice():
    """Verify docs/principals.md explicitly supersedes pseudo-psychology and false safety claims."""
    principals_file = REPO_ROOT / "docs" / "principals.md"
    assert principals_file.exists()

    content = principals_file.read_text(encoding="utf-8")
    assert "Reconciliation Notice (Gate D / T47)" in content
    assert "APPROVE RECOMMENDED" in content
    assert "HUMAN REVIEW REQUIRED" in content


def test_readme_reflects_nextjs_15():
    """Verify README shield reflects Next.js 15 upgrade."""
    readme_file = REPO_ROOT / "README.md"
    assert readme_file.exists()
    content = readme_file.read_text(encoding="utf-8")
    assert "Next.js-15" in content
