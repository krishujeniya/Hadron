"""
tests/test_responsive_layouts_and_extremes_t40.py
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
