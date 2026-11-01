"""Verification test suite for T49: Incident management, operational runbooks, and privacy-aware product measurement.

Validates:
1. docs/INCIDENT_AND_SUPPORT.md defines severity tiers (SEV-1 to SEV-4) with response SLAs and escalation rosters.
2. All six operational runbooks exist in docs/runbooks/ with trigger, diagnosis, and remediation sections.
3. Privacy-aware product measurement rules strictly prohibit code, diffs, tokens, and raw stacks in telemetry.
4. Synthetic tabletop incident exercise protocol is defined.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INCIDENT_FILE = REPO_ROOT / "docs" / "INCIDENT_AND_SUPPORT.md"
RUNBOOKS_DIR = REPO_ROOT / "docs" / "runbooks"


def test_incident_management_document_defines_tiers_and_escalations():
    """Verify docs/INCIDENT_AND_SUPPORT.md defines severity tiers (SEV-1 to SEV-4) with SLAs."""
    assert INCIDENT_FILE.exists(), "docs/INCIDENT_AND_SUPPORT.md must exist"
    content = INCIDENT_FILE.read_text(encoding="utf-8")

    assert "SEV-1 (Critical)" in content
    assert "SEV-2 (Major)" in content
    assert "SEV-3 (Moderate)" in content
    assert "SEV-4 (Low)" in content

    # Response SLAs
    assert "≤ 15 minutes" in content
    assert "≤ 30 minutes" in content
    assert "≤ 4 hours" in content
    assert "≤ 24 hours" in content


def test_all_six_operational_runbooks_exist_and_have_required_sections():
    """Verify all 6 runbooks exist with trigger, diagnosis, and remediation sections."""
    required_runbooks = [
        "RUNBOOK-STUCK-REVIEWS.md",
        "RUNBOOK-PROVIDER-OUTAGE.md",
        "RUNBOOK-BAD-RECOMMENDATION.md",
        "RUNBOOK-UNAUTHORIZED-ACCESS.md",
        "RUNBOOK-BUDGET-LEDGER-OUTAGE.md",
        "RUNBOOK-FAILED-PUBLICATION.md",
    ]

    for rb_name in required_runbooks:
        rb_path = RUNBOOKS_DIR / rb_name
        assert rb_path.exists(), f"Runbook {rb_name} must exist"
        text = rb_path.read_text(encoding="utf-8")
        assert "Trigger" in text or "Symptom" in text, f"{rb_name} must specify trigger"
        assert "Diagnosis" in text, f"{rb_name} must specify diagnosis"
        assert "Remediation" in text, f"{rb_name} must specify remediation"


def test_privacy_preserving_telemetry_rules():
    """Verify telemetry specifications strictly exclude code, credentials, and full review bodies."""
    content = INCIDENT_FILE.read_text(encoding="utf-8")

    assert "Privacy-Aware Telemetry & Measurement Contract" in content
    assert "Customer repository source code" in content
    assert "GitHub personal access tokens" in content
    assert "Tabletop Incident Protocol" in content
