"""
Unit and contract tests for T32: Simplify Navigation and Separate Public/Product Surfaces.
Validates public/product surface separation, primary/secondary navigation, aria-current, and 404 recovery.
"""

from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def test_public_solution_surface_separation():
    """Verify Shell.tsx renders dedicated public layout for /solutions routes without auth blocks."""
    shell_path = FRONTEND_DIR / "src" / "components" / "Shell.tsx"
    assert shell_path.exists()
    content = shell_path.read_text(encoding="utf-8")

    assert 'pathname?.startsWith("/solutions")' in content or "isSolutionsRoute" in content
    assert "Sign In to App" in content or "Sign in to App" in content
    assert "Hadron · Autonomous Multi-Agent PR Review Engine" in content


def test_primary_and_secondary_navigation_hierarchy():
    """Verify primary work navigation and secondary operations structure."""
    shell_path = FRONTEND_DIR / "src" / "components" / "Shell.tsx"
    content = shell_path.read_text(encoding="utf-8")

    # Primary navigation routes
    assert 'href: "/", label: "Overview"' in content
    assert 'href: "/reviews", label: "Reviews"' in content
    assert 'href: "/hitl", label: "Human Review"' in content
    assert 'href: "/repositories", label: "Repositories"' in content

    # Secondary operations routes
    assert 'href: "/economics"' in content
    assert 'href: "/health"' in content

    # Aria current on navigation links
    assert 'aria-current={active ? "page" : undefined}' in content


def test_accessible_landmarks_and_controls():
    """Verify skip-link, main landmark, and mobile navigation attributes."""
    shell_path = FRONTEND_DIR / "src" / "components" / "Shell.tsx"
    content = shell_path.read_text(encoding="utf-8")

    assert 'href="#main-content"' in content
    assert 'id="main-content"' in content
    assert 'aria-controls="mobile-nav-drawer"' in content
    assert 'aria-expanded={mobileOpen}' in content


def test_not_found_recovery_page():
    """Verify 404 recovery page provides direct paths back to Overview and Reviews."""
    not_found_path = FRONTEND_DIR / "src" / "app" / "not-found.tsx"
    assert not_found_path.exists(), "not-found.tsx must exist"
    content = not_found_path.read_text(encoding="utf-8")

    assert "Page Not Found" in content or "404" in content
    assert 'href="/"' in content
    assert 'href="/reviews"' in content
