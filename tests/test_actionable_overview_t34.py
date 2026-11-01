"""
Unit and contract tests for T34: Replace the Overview with Actionable Review Information.
Verifies state-aware action prioritization, view mode synchronization, server totals, and actionable grouping.
"""

from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


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


def test_command_palette_and_dashboard_storage_event_sync():
    """Verify CommandPalette writes hadron_view_mode with storage event and Dashboard synchronizes reactively."""
    palette_path = FRONTEND_DIR / "src" / "components" / "CommandPalette.tsx"
    page_path = FRONTEND_DIR / "src" / "app" / "page.tsx"

    palette_content = palette_path.read_text(encoding="utf-8")
    assert 'localStorage.setItem("hadron_view_mode"' in palette_content
    assert 'window.dispatchEvent(new Event("storage"))' in palette_content

    page_content = page_path.read_text(encoding="utf-8")
    assert 'window.addEventListener("storage", syncMode)' in page_content
    assert 'window.removeEventListener("storage", syncMode)' in page_content
