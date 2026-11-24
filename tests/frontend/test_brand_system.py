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
    master = (ASSETS / "ulogo-icon.svg").read_text(encoding="utf-8")
    public = (PUBLIC / "ulogo-favicon.svg").read_text(encoding="utf-8")
    assert master == public
    assert "<svg" in master


def test_wordmarks_have_matching_shapes_and_dark_mode():
    light = (ASSETS / "ulogo-logo.svg").read_text(encoding="utf-8")
    dark = (ASSETS / "ulogo-logo-dark.svg").read_text(encoding="utf-8")
    assert light == (PUBLIC / "ulogo-logo.svg").read_text(encoding="utf-8")
    assert dark == (PUBLIC / "ulogo-logo-dark.svg").read_text(encoding="utf-8")


def test_ui_components_and_readme_use_the_new_logo():
    icon = (ROOT / "frontend/src/components/brand/HadronIcon.tsx").read_text()
    logo = (ROOT / "frontend/src/components/brand/HadronLogo.tsx").read_text()
    readme = (ROOT / "README.md").read_text()
    assert 'viewBox="0 0 256 256"' in icon
    assert "/ulogo-logo.svg" in logo and "/ulogo-logo-dark.svg" in logo
    assert "assets/ulogo-logo.png" in readme
    assert 'alt="Hadron' in readme


def test_social_master_and_export_pipeline():
    assert (PUBLIC / "ulogo-og-image.png").is_file()
    assert (ASSETS / "ulogo-og-image.png").is_file()
    assert (ROOT / "docs/design/BRAND.md").is_file()


def test_raster_exports_match_repository_and_public_variants():
    """Generated binaries in README and website must not silently diverge."""
    pairs = (
        ("assets/ulogo-logo.png", "frontend/public/ulogo-logo.png"),
        ("assets/ulogo-icon-512.png", "frontend/public/ulogo-icon-512.png"),
        ("assets/ulogo-og-image.png", "frontend/public/ulogo-og-image.png"),
    )
    for first, second in pairs:
        a = ROOT / first
        b = ROOT / second
        assert a.is_file() and b.is_file(), (first, second)
        assert a.read_bytes() == b.read_bytes(), f"Brand mismatch between {first} and {second}"
        assert len(a.read_bytes()) > 1000, f"Unexpectedly empty export: {first}"
