"""
Unit and contract tests for T31: Semantic Design System and Complete Themes.
Validates CSS variables, Tailwind tokens, theme state machine, and UI component contracts.
"""

from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def test_globals_css_semantic_token_contract():
    """Verify globals.css contains the exact WCAG-tested semantic tokens from Tracker Section 8."""
    css_path = FRONTEND_DIR / "src" / "app" / "globals.css"
    assert css_path.exists(), "globals.css must exist"
    content = css_path.read_text(encoding="utf-8")

    # Dark mode tokens
    assert "--bg: 11 18 32" in content, "Dark Canvas must be #0B1220 (11 18 32)"
    assert "--surface: 17 24 39" in content, "Dark Surface must be #111827 (17 24 39)"
    assert "--panel: 30 41 59" in content, "Dark Raised surface must be #1E293B (30 41 59)"
    assert "--foreground: 248 250 252" in content, "Dark Primary text must be #F8FAFC (248 250 252)"
    assert "--muted: 203 213 225" in content, "Dark Secondary text must be #CBD5E1 (203 213 225)"
    assert "--accent: 147 197 253" in content, "Dark Link/accent text must be #93C5FD (147 197 253)"
    assert "--primary-action: 29 78 216" in content, "Primary action bg must be #1D4ED8 (29 78 216)"
    assert "--separator: 51 65 85" in content, "Dark Separator must be #334155 (51 65 85)"
    assert "--border: 148 163 184" in content, "Dark Control boundary must be #94A3B8 (148 163 184)"
    assert "--ok: 134 239 172" in content, "Dark Success text must be #86EFAC (134 239 172)"
    assert "--warn: 253 230 138" in content, "Dark Warning text must be #FDE68A (253 230 138)"
    assert "--err: 252 165 165" in content, "Dark Error text must be #FCA5A5 (252 165 165)"

    # Light mode tokens
    assert "--bg: 248 250 252" in content, "Light Canvas must be #F8FAFC (248 250 252)"
    assert "--surface: 255 255 255" in content, "Light Surface must be #FFFFFF (255 255 255)"
    assert "--panel: 241 245 249" in content, "Light Raised surface must be #F1F5F9 (241 245 249)"
    assert "--foreground: 15 23 42" in content, "Light Primary text must be #0F172A (15 23 42)"
    assert "--muted: 71 85 105" in content, "Light Secondary text must be #475569 (71 85 105)"
    assert "--accent: 29 78 216" in content, "Light Link/accent text must be #1D4ED8 (29 78 216)"
    assert "--separator: 203 213 225" in content, "Light Separator must be #CBD5E1 (203 213 225)"
    assert "--border: 100 116 139" in content, "Light Control boundary must be #64748B (100 116 139)"
    assert "--ok: 22 101 52" in content, "Light Success text must be #166534 (22 101 52)"
    assert "--warn: 146 64 14" in content, "Light Warning text must be #92400E (146 64 14)"
    assert "--err: 185 28 28" in content, "Light Error text must be #B91C1C (185 28 28)"

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
    shell_path = FRONTEND_DIR / "src" / "components" / "Shell.tsx"
    assert shell_path.exists(), "Shell.tsx must exist"
    content = shell_path.read_text(encoding="utf-8")

    assert "GitHubAccountModal" in content, "GitHubAccountModal must be mounted in Shell"
    assert 'href="#main-content"' in content, "Skip to content link must exist"
    assert 'aria-current=' in content, "Navigation must indicate aria-current for active route"
    assert 'PRIMARY_NAV' in content
    assert 'SECONDARY_NAV' in content
