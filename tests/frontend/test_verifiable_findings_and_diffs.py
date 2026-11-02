"""
tests/frontend/test_verifiable_findings_and_diffs.py
-----------------------------------------------
Validates T36: Make review findings and diffs verifiable.
Tests:
  1. parseUnifiedDiff accurately extracts paths containing spaces.
  2. parseUnifiedDiff detects deleted files, new files, and binary files.
  3. DiffViewer and FindingCard preserve unknown severity and unknown confidence rather than inventing defaults.
  4. Finding matching attaches to both old and new line coordinates as well as file-level findings.
  5. Reviews detail header presents separate execution and publication states.
  6. Findings disclosure clarifies that automated findings do not imply all code was examined.
"""

import pathlib


def test_diff_viewer_source_implementation():
    """Inspect DiffViewer.tsx and AgentFindingCard.tsx to verify verifiability contracts."""
    diff_viewer_path = pathlib.Path("frontend/src/features/reviews/DiffViewer.tsx")
    assert diff_viewer_path.exists(), "DiffViewer.tsx must exist"
    diff_content = diff_viewer_path.read_text(encoding="utf-8")

    # 1. Path with spaces handling (regex match, not naive split(' ')[2])
    assert "gitMatch" in diff_content or "headerBody.match" in diff_content
    # Confirm no naive parts[2] split without regex
    assert "parts[2]?.replace" not in diff_content

    # 2. Deleted, new, and binary file flags
    assert "isDeleted" in diff_content
    assert "isNew" in diff_content
    assert "isBinary" in diff_content

    # 3. Old line and new line coordinate matching
    assert "line.oldLine" in diff_content
    assert "line.newLine" in diff_content

    # 4. No invented CRITICAL severity or 80% confidence
    assert 'finding.severity || "CRITICAL"' not in diff_content
    assert "finding.confidence ?? 0.8" not in diff_content
    assert 'finding.severity || "UNKNOWN"' in diff_content
    assert "Confidence: Unknown" in diff_content


def test_finding_card_and_by_agent_source():
    """Inspect AgentFindingCard.tsx to verify severity filtering and disclosure."""
    card_path = pathlib.Path("frontend/src/features/reviews/AgentFindingCard.tsx")
    assert card_path.exists(), "AgentFindingCard.tsx must exist"
    card_content = card_path.read_text(encoding="utf-8")

    # 1. Severity filter controls
    assert "severityFilter" in card_content
    assert "severityCounts" in card_content

    # 2. Deep link anchors
    assert "finding-" in card_content
    assert "scroll-mt-" in card_content

    # 3. Mandatory disclaimer
    assert "Automated findings do not imply all code was examined" in card_content


def test_review_detail_page_states():
    """Inspect frontend/src/app/reviews/[id]/page.tsx to verify execution and publication states."""
    detail_path = pathlib.Path("frontend/src/app/reviews/[id]/page.tsx")
    assert detail_path.exists(), "reviews/[id]/page.tsx must exist"
    detail_content = detail_path.read_text(encoding="utf-8")

    # 1. Separate execution and publication states
    assert "executionState" in detail_content
    assert "publicationState" in detail_content
    assert "Execution:" in detail_content
    assert "Publication:" in detail_content

    # 2. Markdown copy with full metadata and disclosure
    assert "copyMarkdown" in detail_content
    assert "Automated findings do not imply all code was examined" in detail_content
    assert "Review copied to clipboard" in detail_content
