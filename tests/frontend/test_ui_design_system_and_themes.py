"""
Unit and contract tests for T31: Semantic Design System and Complete Themes.
Validates CSS variables, Tailwind tokens, theme state machine, and UI component contracts.
"""

from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def test_globals_css_semantic_token_contract():
    """Verify globals.css contains the exact WCAG-tested semantic tokens from Tracker Section 8."""
    css_path = FRONTEND_DIR / "src" / "app" / "globals.css"
    assert css_path.exists(), "globals.css must exist"
    content = css_path.read_text(encoding="utf-8")

    # Dark mode tokens (Grok monochrome)
    assert "--bg: 0 0 0" in content, "Dark Canvas must be #000000 (0 0 0)"
    assert "--surface: 10 10 12" in content, "Dark Surface must be #0A0A0C (10 10 12)"
    assert "--panel: 22 22 26" in content, "Dark Raised surface must be #16161A (22 22 26)"
    assert "--foreground: 255 255 255" in content, "Dark Primary text must be #FFFFFF (255 255 255)"
    assert "--muted: 161 161 170" in content, "Dark Secondary text must be #A1A1AA (161 161 170)"
    assert "--accent: 255 255 255" in content, "Dark Link/accent text must be #FFFFFF (255 255 255)"
    assert "--primary-action: 255 255 255" in content, "Primary action bg must be #FFFFFF (255 255 255)"
    assert "--separator: 39 39 42" in content, "Dark Separator must be #27272A (39 39 42)"
    assert "--border: 63 63 70" in content, "Dark Control boundary must be #3F3F46 (63 63 70)"
    assert "--ok: 244 244 245" in content, "Dark Success text must be #F4F4F5 (244 244 245)"
    assert "--warn: 212 212 216" in content, "Dark Warning text must be #D4D4D8 (212 212 216)"
    assert "--err: 255 255 255" in content, "Dark Error text must be #FFFFFF (255 255 255)"

    # Light mode tokens (Grok inverted monochrome)
    assert "--bg: 255 255 255" in content, "Light Canvas must be #FFFFFF (255 255 255)"
    assert "--surface: 250 250 250" in content, "Light Surface must be #FAFAFA (250 250 250)"
    assert "--panel: 244 244 245" in content, "Light Raised surface must be #F4F4F5 (244 244 245)"
    assert "--foreground: 0 0 0" in content, "Light Primary text must be #000000 (0 0 0)"
    assert "--muted: 113 113 122" in content, "Light Secondary text must be #71717A (113 113 122)"
    assert "--accent: 0 0 0" in content, "Light Link/accent text must be #000000 (0 0 0)"
    assert "--primary-action: 0 0 0" in content, "Light Primary action bg must be #000000 (0 0 0)"
    assert "--separator: 228 228 231" in content, "Light Separator must be #E4E4E7 (228 228 231)"
    assert "--border: 212 212 216" in content, "Light Control boundary must be #D4D4D8 (212 212 216)"
    assert "--ok: 24 24 27" in content, "Light Success text must be #18181B (24 24 27)"
    assert "--warn: 63 63 70" in content, "Light Warning text must be #3F3F46 (63 63 70)"
    assert "--err: 0 0 0" in content, "Light Error text must be #000000 (0 0 0)"

    # Focus outline
    assert ":focus-visible" in content, "Must declare accessible visible focus outline"
    assert "outline: 2px solid rgb(var(--accent))" in content


def test_tailwind_config_exports_all_semantic_tokens():
    """Verify tailwind.config.ts maps all semantic colors to CSS variables."""
    tw_path = FRONTEND_DIR / "tailwind.config.ts"
    assert tw_path.exists(), "tailwind.config.ts must exist"
    content = tw_path.read_text(encoding="utf-8")

    expected_tokens = [
        "bg", "panel", "surface", "border", "separator",
        "muted", "accent", "primary-action", "foreground",
        "ok", "warn", "err"
    ]
    for token in expected_tokens:
        assert f'"{token}":' in content or f"{token}:" in content, f"Token {token} missing in tailwind colors"


def test_theme_context_and_provider():
    """Verify single theme source of truth with light/dark/system support and storage guards."""
    theme_path = FRONTEND_DIR / "src" / "lib" / "themeContext.tsx"
    assert theme_path.exists(), "themeContext.tsx must exist"
    content = theme_path.read_text(encoding="utf-8")

    assert 'type Theme = "light" | "dark" | "system"' in content
    assert 'prefers-color-scheme: dark' in content
    assert 'addEventListener("storage"' in content
    assert 'try {' in content and 'localStorage.getItem' in content
    assert 'suppressHydrationWarning' in (FRONTEND_DIR / "src" / "app" / "layout.tsx").read_text(encoding="utf-8")


def test_reusable_ui_primitives_exist_and_conform():
    """Verify Button, Field, Status, Alert, Dialog, EmptyState, PageHeader primitives exist."""
    ui_dir = FRONTEND_DIR / "src" / "components" / "ui"
    assert ui_dir.exists(), "components/ui directory must exist"

    # Button
    button_content = (ui_dir / "Button.tsx").read_text(encoding="utf-8")
    assert "isLoading" in button_content
    assert "focus-visible:ring-accent" in button_content
    assert "aria-busy" in button_content

    # Field
    field_content = (ui_dir / "Field.tsx").read_text(encoding="utf-8")
    assert "aria-invalid" in field_content
    assert "aria-describedby" in field_content
    assert 'role="alert"' in field_content

    # Status
    status_content = (ui_dir / "Status.tsx").read_text(encoding="utf-8")
    assert "border-ok/30" in status_content
    assert "border-warn/30" in status_content
    assert "border-err/30" in status_content

    # Alert
    alert_content = (ui_dir / "Alert.tsx").read_text(encoding="utf-8")
    assert 'role="alert"' in alert_content

    # Dialog
    dialog_content = (ui_dir / "Dialog.tsx").read_text(encoding="utf-8")
    assert 'role="dialog"' in dialog_content
    assert 'aria-modal="true"' in dialog_content
    assert "aria-labelledby" in dialog_content

    # EmptyState
    empty_content = (ui_dir / "EmptyState.tsx").read_text(encoding="utf-8")
    assert "border-dashed" in empty_content

    # PageHeader
    header_content = (ui_dir / "PageHeader.tsx").read_text(encoding="utf-8")
    assert "PageHeader" in header_content


def test_shell_navigation_and_mounts():
    """Verify Shell implements primary/secondary navigation, skip link, and mounts GitHubAccountModal."""
    shell_path = FRONTEND_DIR / "src" / "components" / "layout" / "Shell.tsx"
    assert shell_path.exists(), "Shell.tsx must exist"
    content = shell_path.read_text(encoding="utf-8")

    assert "GitHubAccountModal" in content, "GitHubAccountModal must be mounted in Shell"
    assert 'href="#main-content"' in content, "Skip to content link must exist"
    assert 'aria-current=' in content, "Navigation must indicate aria-current for active route"
    assert 'PRIMARY_NAV' in content
    assert 'SECONDARY_NAV' in content
