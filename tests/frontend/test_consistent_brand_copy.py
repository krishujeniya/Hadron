"""Verification test suite for T43: Brand, copy, and feedback consistency.

Validates:
1. Public brand assets exist, are valid PNG/SVG images, and match expected dimensions.
2. Review summary terminology matches the standard contract:
   - "Hadron Review" header
   - Recommendations: "APPROVE RECOMMENDED", "CHANGES RECOMMENDED", "HUMAN REVIEW REQUIRED"
   - Limitations disclaimer in footer
3. No fake urgency, streak counters, or deceptive certainty claims.
"""

from pathlib import Path
import struct
from backend.models.enums import ReviewVerdict
from backend.orchestrator.nodes import _build_review_summary

REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_DIR = REPO_ROOT / "frontend" / "public"


def _get_png_dimensions(path: Path) -> tuple[int, int]:
    """Parse width and height from PNG IHDR chunk."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a valid PNG file"
    w, h = struct.unpack(">II", data[16:24])
    return w, h


def test_brand_assets_exist_and_have_exact_dimensions():
    """Verify all brand assets in frontend/public exist with valid formats and dimensions."""
    expected_assets = {
        "apple-touch-icon.png": (180, 180),
        "favicon-16x16.png": (16, 16),
        "favicon-32x32.png": (32, 32),
        "icon-192.png": (192, 192),
        "icon-512.png": (512, 512),
        "og-image.png": (1200, 630),
    }

    for filename, (expected_w, expected_h) in expected_assets.items():
        file_path = PUBLIC_DIR / filename
        assert file_path.exists(), f"Brand asset {filename} must exist"
        w, h = _get_png_dimensions(file_path)
        assert (w, h) == (expected_w, expected_h), f"{filename} dimensions {w}x{h} != expected {expected_w}x{expected_h}"

    # SVGs
    for svg_name in ["favicon.svg", "logo.svg"]:
        svg_path = PUBLIC_DIR / svg_name
        assert svg_path.exists(), f"SVG asset {svg_name} must exist"
        text = svg_path.read_text(encoding="utf-8")
        assert "<svg" in text, f"{svg_name} must contain <svg root element"


def test_review_summary_terminology_and_disclaimer():
    """Verify GitHub review summary uses honest recommendation labels and explicit limitation disclaimer."""
    state_approve = {
        "verdict": ReviewVerdict.APPROVE,
        "final_findings": [],
        "overall_confidence": 0.92,
        "agent_results": [{"agent_type": "security", "success": True, "findings": [], "confidence": 0.95}],
        "workflow_id": "wf-brand-test-1",
        "head_commit_sha": "abc1234",
        "base_branch": "main",
    }
    summary_approve = _build_review_summary(state_approve)
    assert "## 🤖 Hadron Review" in summary_approve
    assert "APPROVE RECOMMENDED" in summary_approve
    assert "No blocking issues identified" in summary_approve
    assert "does not guarantee complete absence of defects" in summary_approve

    state_changes = {
        "verdict": ReviewVerdict.REQUEST_CHANGES,
        "final_findings": [{"severity": "high", "summary": "SQL Injection", "file_path": "db.py", "line_start": 42}],
        "overall_confidence": 0.85,
        "agent_results": [{"agent_type": "security", "success": True, "findings": [{}], "confidence": 0.85}],
        "workflow_id": "wf-brand-test-2",
        "head_commit_sha": "abc1234",
        "base_branch": "main",
    }
    summary_changes = _build_review_summary(state_changes)
    assert "CHANGES RECOMMENDED" in summary_changes

    state_human = {
        "verdict": ReviewVerdict.NEEDS_HUMAN_REVIEW,
        "final_findings": [],
        "overall_confidence": 0.40,
        "agent_results": [],
        "workflow_id": "wf-brand-test-3",
        "head_commit_sha": "abc1234",
        "base_branch": "main",
    }
    summary_human = _build_review_summary(state_human)
    assert "HUMAN REVIEW REQUIRED" in summary_human


def test_absence_of_hype_and_fake_urgency_words():
    """Verify absence of manipulative copy like streaks, magic, or guaranteed safety."""
    frontend_src = REPO_ROOT / "frontend" / "src"
    prohibited_terms = ["streak", "golden ratio", "magical", "100% secure", "guaranteed safe"]

    for file_path in frontend_src.rglob("*.tsx"):
        content = file_path.read_text(encoding="utf-8").lower()
        for term in prohibited_terms:
            assert term not in content, f"Prohibited term '{term}' found in {file_path}"
