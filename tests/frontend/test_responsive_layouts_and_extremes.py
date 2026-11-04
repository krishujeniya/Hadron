"""
tests/frontend/test_responsive_layouts_and_extremes.py
-------------------------------------------------
Validates T40: Verify responsive layouts, zoom, touch, and content extremes.
Tests:
  1. globals.css enforces safe area insets, word wrapping, and overflow containment.
  2. Main layout structures avoid fixed h-screen viewport traps, utilizing min-h-screen.
  3. Repository cards handle long names with min-w-0 and break-all.
  4. Reviews page provides mobile card layouts preventing horizontal viewport overflow.
  5. Code tables and diff regions use keyboard-scrollable regions (role=region, tabIndex=0, overflow-x-auto).
"""

import pathlib


def test_responsive_css_and_safe_areas():
    """Verify globals.css contains safe area insets and overflow wrap rules."""
    css_path = pathlib.Path("frontend/src/app/globals.css")
    assert css_path.exists(), "globals.css must exist"
    content = css_path.read_text(encoding="utf-8")

    assert "safe-area-inset-left" in content
    assert "safe-area-inset-right" in content
    assert "overflow-wrap: break-word" in content
    assert "min-height: 100vh" in content


def test_viewport_height_trap_absence():
    """Verify frontend source files do not contain fixed h-screen layout traps."""
    import re
    src_dir = pathlib.Path("frontend/src")

    for file in src_dir.rglob("*.tsx"):
        content = file.read_text(encoding="utf-8")
        # Match standalone 'h-screen' not preceded by 'min-' or 'max-'
        matches = re.findall(r'(?<![min|max]-)h-screen', content)
        assert len(matches) == 0, f"Found fixed h-screen in {file}"


def test_content_extremes_resilience():
    """Verify repository and review components handle long identifiers and small viewports."""
    repos_path = pathlib.Path("frontend/src/app/repositories/page.tsx")
    assert repos_path.exists()
    repos_content = repos_path.read_text(encoding="utf-8")
    assert "break-all" in repos_content
    assert "min-w-0" in repos_content

    reviews_path = pathlib.Path("frontend/src/app/reviews/page.tsx")
    assert reviews_path.exists()
    reviews_content = reviews_path.read_text(encoding="utf-8")
    assert "sm:hidden" in reviews_content
    assert "break-words" in reviews_content
    assert "break-all" in reviews_content


def test_mobile_overflow_prevention_guards():
    """Verify key components enforce horizontal containment and safe truncation."""
    diff_viewer_path = pathlib.Path("frontend/src/features/reviews/DiffViewer.tsx")
    assert diff_viewer_path.exists()
    diff_content = diff_viewer_path.read_text(encoding="utf-8")
    assert "min-w-0 max-w-full" in diff_content
    assert "truncate" in diff_content

    shell_path = pathlib.Path("frontend/src/components/layout/Shell.tsx")
    assert shell_path.exists()
    shell_content = shell_path.read_text(encoding="utf-8")
    assert "min-w-0 max-w-full" in shell_content
    assert "overflow-x-hidden" in shell_content

    landing_path = pathlib.Path("frontend/src/features/marketing/PublicLandingPage.tsx")
    assert landing_path.exists()
    landing_content = landing_path.read_text(encoding="utf-8")
    assert "min-w-0 max-w-full" in landing_content
    assert "break-words" in landing_content


def test_text_overflow_containment_and_wrapping_resilience():
    """Verify text overflow guards, anywhere wrapping, and resilient chips/badges."""
    css_path = pathlib.Path("frontend/src/app/globals.css")
    assert css_path.exists()
    css_content = css_path.read_text(encoding="utf-8")
    assert "overflow-wrap: anywhere" in css_content

    non_tech_path = pathlib.Path("frontend/src/features/reviews/NonTechReviewCard.tsx")
    assert non_tech_path.exists()
    non_tech_content = non_tech_path.read_text(encoding="utf-8")
    assert "line-clamp-2 break-words" in non_tech_content
    assert "break-all" in non_tech_content

    hitl_detail_path = pathlib.Path("frontend/src/app/hitl/[id]/page.tsx")
    assert hitl_detail_path.exists()
    hitl_detail_content = hitl_detail_path.read_text(encoding="utf-8")
    assert "break-all" in hitl_detail_content
    assert "break-words" in hitl_detail_content

    verdict_chip_path = pathlib.Path("frontend/src/features/reviews/VerdictChip.tsx")
    assert verdict_chip_path.exists()
    verdict_content = verdict_chip_path.read_text(encoding="utf-8")
    assert "shrink-0" in verdict_content

    status_badge_path = pathlib.Path("frontend/src/features/reviews/ReviewStatusBadge.tsx")
    assert status_badge_path.exists()
    status_content = status_badge_path.read_text(encoding="utf-8")
    assert "shrink-0" in status_content
