"""
Unit and contract tests for T34: Replace the Overview with Actionable Review Information.
Verifies state-aware action prioritization, view mode synchronization, server totals, and actionable grouping.
"""

from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def test_overview_action_prioritization_and_sections():
    """Verify app/page.tsx segments reviews into actionable buckets and prioritizes action banner."""
    page_path = FRONTEND_DIR / "src" / "app" / "page.tsx"
    assert page_path.exists()
    content = page_path.read_text(encoding="utf-8")

    # State-aware buckets
    assert "pendingHitl" in content
    assert "runningReviews" in content
    assert "failedReviews" in content
    assert "recentReviews" in content

    # Server totals rather than page subset
    assert "reviewsResp?.total" in content
    assert "hitlResp?.total" in content

    # Prioritization checks
    assert "pendingHitl.length > 0" in content
    assert "failedReviews.length > 0" in content
    assert "runningReviews.length > 0" in content
    assert "repositories.length === 0" in content


def test_dashboard_has_one_layout_regardless_of_saved_mode():
    """Legacy view preferences must not select a second production UI."""
    palette = (FRONTEND_DIR / "src/components/layout/CommandPalette.tsx").read_text()
    page = (FRONTEND_DIR / "src/app/page.tsx").read_text()
    assert "hadron_view_mode" not in palette + page
    assert "viewMode" not in page
    assert "Review overview" in page
    assert "Plain-language guidance" in page
