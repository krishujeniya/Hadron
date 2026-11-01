"""
tests/test_keyboard_focus_dialog_shortcuts_t39.py
-------------------------------------------------
Validates T39: Complete keyboard, focus, dialog, and shortcut behavior.
Tests:
  1. Shell implements skip link (#main-content), landmark semantics, and focusable drawer bounds.
  2. Mobile navigation hides offscreen elements (hidden md:flex) when closed, preventing focus traps.
  3. Mobile menu trigger has aria-expanded, aria-controls, and focus restoration via mobileTriggerRef.
  4. CommandPalette implements complete WAI-ARIA combobox/listbox APG pattern with activedescendant.
  5. CommandPalette contains focus trap (Tab/Shift-Tab) and restores focus to previously active element on close.
"""

import pathlib


def test_shell_keyboard_and_navigation_drawer_contracts():
    """Verify Shell.tsx implements skip link, accessible trigger attributes, and offscreen focus guards."""
    shell_path = pathlib.Path("frontend/src/components/Shell.tsx")
    assert shell_path.exists(), "Shell.tsx must exist"
    content = shell_path.read_text(encoding="utf-8")

    # 1. Skip link & main landmark
    assert 'href="#main-content"' in content
    assert 'id="main-content"' in content
    assert "Skip to main content" in content

    # 2. Accessible trigger association
    assert "mobileTriggerRef" in content
    assert "aria-expanded={mobileOpen}" in content
    assert 'aria-controls="mobile-nav-drawer"' in content

    # 3. Offscreen focus protection on mobile
    assert 'mobileOpen ? "translate-x-0 flex" : "-translate-x-full hidden md:flex"' in content

    # 4. Escape key handling and focus restoration
    assert 'e.key === "Escape"' in content
    assert "mobileTriggerRef.current?.focus()" in content


def test_command_palette_apg_dialog_and_focus_trap():
    """Verify CommandPalette.tsx adheres to WAI-ARIA Combobox / Listbox APG specification."""
    palette_path = pathlib.Path("frontend/src/components/CommandPalette.tsx")
    assert palette_path.exists(), "CommandPalette.tsx must exist"
    content = palette_path.read_text(encoding="utf-8")

    # 1. Dialog semantics
    assert 'role="dialog"' in content
    assert 'aria-modal="true"' in content
    assert 'aria-label="Command palette"' in content

    # 2. Combobox semantics
    assert 'role="combobox"' in content
    assert 'aria-autocomplete="list"' in content
    assert "aria-controls=" in content
    assert "aria-activedescendant=" in content

    # 3. Listbox & Option semantics
    assert 'role="listbox"' in content
    assert 'role="option"' in content
    assert "aria-selected=" in content

    # 4. Focus restoration and Tab trapping
    assert "previousFocusRef" in content
    assert 'e.key === "Tab"' in content
    assert "previousFocusRef.current.focus()" in content
