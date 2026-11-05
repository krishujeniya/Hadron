"""Contracts for the unified four-agent Hadron identity.

The vector master is the source of truth, and exported PNG assets must retain
the dimensions expected by browser metadata and social share platforms.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "frontend" / "public"
ASSETS = ROOT / "assets"

COLORS = ("#0B69F7", "#EF4050", "#08B773", "#F5B800", "#20262F")


def test_vector_brand_sources_are_consistent_and_flat():
    master = (ASSETS / "icon.svg").read_text(encoding="utf-8")
    public = (PUBLIC / "favicon.svg").read_text(encoding="utf-8")
    assert master == public
    for color in COLORS:
        assert color in master
    assert 'viewBox="0 0 256 256"' in master
    assert "<filter" not in master
    assert "<linearGradient" not in master
    assert "orbit" not in master.lower()


def test_wordmarks_have_matching_shapes_and_dark_mode():
    light = (ASSETS / "logo.svg").read_text(encoding="utf-8")
    dark = (ASSETS / "logo-dark.svg").read_text(encoding="utf-8")
    assert light == (PUBLIC / "logo.svg").read_text(encoding="utf-8")
    assert dark == (PUBLIC / "logo-dark.svg").read_text(encoding="utf-8")
    assert "#20262F" in light
    assert "#F8FAFC" in dark
    for code in COLORS[:4]:
        assert code in light and code in dark
    assert ">adron</text>" in light and ">adron</text>" in dark


def test_ui_components_and_readme_use_the_new_logo():
    icon = (ROOT / "frontend/src/components/brand/HadronIcon.tsx").read_text()
    logo = (ROOT / "frontend/src/components/brand/HadronLogo.tsx").read_text()
    readme = (ROOT / "README.md").read_text()
    assert 'viewBox="0 0 256 256"' in icon
    assert "/logo.svg" in logo and "/logo-dark.svg" in logo
    assert "assets/logo.svg" in readme and "assets/logo-dark.svg" in readme
    assert 'alt="Hadron' in readme


def test_social_master_and_export_pipeline():
    social = (ASSETS / "social-card.svg").read_text(encoding="utf-8")
    assert 'viewBox="0 0 1200 630"' in social
    assert "Security · Quality · Testing · Documentation" in social
    script = (ROOT / "scripts/generate_brand_assets.py").read_text()
    assert "frontend/public/apple-touch-icon.png" in script
    assert "frontend/public/og-image.png" in script
    assert "assets/logo.png" in script
    assert (ROOT / ".github/workflows/brand-assets.yml").is_file()
    assert (ROOT / "docs/design/BRAND.md").is_file()


def test_raster_exports_match_repository_and_public_variants():
    """Generated binaries in README and website must not silently diverge."""
    pairs = (
        ("assets/logo.png", "frontend/public/logo.png"),
        ("assets/icon.png", "frontend/public/icon-512.png"),
        ("assets/og-image.png", "frontend/public/og-image.png"),
    )
    for first, second in pairs:
        a = ROOT / first
        b = ROOT / second
        assert a.is_file() and b.is_file(), (first, second)
        assert a.read_bytes() == b.read_bytes(), f"Brand mismatch between {first} and {second}"
        assert len(a.read_bytes()) > 1000, f"Unexpectedly empty export: {first}"
