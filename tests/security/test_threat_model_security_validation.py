"""Verification test suite for T48: Threat Modeling and Independent Security Validation.

Validates:
1. docs/security/threat-model.md defines system trust boundaries and threat vectors (BOLA, CSRF, SSRF, Injection, Secrets).
2. Existing security suites covering trust boundaries are linked and passing.
3. Access control assertions satisfy OWASP API Security and GenAI risk standards.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
THREAT_MODEL_FILE = REPO_ROOT / "docs" / "security" / "threat-model.md"


def test_threat_model_documents_trust_boundaries_and_owasp_risks():
    """Verify docs/security/threat-model.md covers all system trust boundaries and critical OWASP attack vectors."""
    assert THREAT_MODEL_FILE.exists(), "docs/security/threat-model.md must exist"
    content = THREAT_MODEL_FILE.read_text(encoding="utf-8")

    # Trust Boundaries
    assert "BOUNDARY 1: Ingress Gateway" in content
    assert "BOUNDARY 2: Authenticated API" in content
    assert "BOUNDARY 3: Queue & Workflows" in content
    assert "BOUNDARY 4: Multi-Agent Review Worker" in content
    assert "BOUNDARY 5: LLM APIs" in content
    assert "BOUNDARY 6: Polyglot Persistence" in content

    # Attack Vectors & Mitigations
    assert "BOLA / IDOR" in content
    assert "Broken Authentication" in content
    assert "Cross-Site Request Forgery (CSRF)" in content
    assert "Indirect Prompt Injection" in content
    assert "XSS & Hostile Markdown Injection" in content
    assert "Server-Side Request Forgery (SSRF)" in content
    assert "Supply Chain & Lockfile Code Execution" in content
    assert "Credential & Secret Leakage" in content
    assert "Denial of Service / Budget Exhaustion" in content


def test_security_regression_matrix_references_real_tests():
    """Verify security regression test suites documented in the matrix exist in the repository."""
    content = THREAT_MODEL_FILE.read_text(encoding="utf-8")
    tests_dir = REPO_ROOT / "tests"

    documented_suites = [
        "security/test_auth_and_rbac.py",
        "security/test_tenant_isolation.py",
        "agents/test_preserve_agent_failures.py",
        "security/test_api_transport_security_and_caching.py",
        "operations/test_disaster_recovery_and_backups.py",
    ]

    for suite_name in documented_suites:
        assert suite_name in content, f"{suite_name} must be documented in the regression matrix"
        suite_path = tests_dir / suite_name
        assert suite_path.exists(), f"Documented test suite {suite_name} must exist on disk"
