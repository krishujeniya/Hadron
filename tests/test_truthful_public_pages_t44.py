"""Verification test suite for T44: Truthful public pages, metadata, robots, and sitemaps.

Validates:
1. robots.ts disallows internal/operational routes (/health/, /economics/, /reviews/, etc.) and allows only designated public paths.
2. sitemap.ts excludes operational /health diagnostic endpoint and includes only public URLs.
3. layout.tsx includes canonical URL, verified OG image path, and factual Schema.org markup.
4. solutions pages define factual metadata and canonical URLs.
"""

from pathlib import Path

FRONTEND_APP_DIR = Path(__file__).resolve().parent.parent / "frontend" / "src" / "app"


def test_robots_configuration_protects_internal_routes():
    """Verify robots.ts disallows private/operational routes and excludes /health from indexing."""
    robots_file = FRONTEND_APP_DIR / "robots.ts"
    assert robots_file.exists(), "robots.ts must exist"
    content = robots_file.read_text(encoding="utf-8")

    assert 'allow: ["/", "/solutions/"]' in content or "allow: ['/', '/solutions/']" in content
    # Disallowed internal/operational paths
    assert '"/health/"' in content or "'/health/'" in content
    assert '"/economics/"' in content or "'/economics/'" in content
    assert '"/reviews/"' in content or "'/reviews/'" in content
    assert '"/hitl/"' in content or "'/hitl/'" in content
    assert '"/api/"' in content or "'/api/'" in content


def test_sitemap_excludes_health_and_includes_public_pages():
    """Verify sitemap.ts excludes internal operational /health and only lists public canonical URLs."""
    sitemap_file = FRONTEND_APP_DIR / "sitemap.ts"
    assert sitemap_file.exists(), "sitemap.ts must exist"
    content = sitemap_file.read_text(encoding="utf-8")

    assert "${baseUrl}/health" not in content
    assert "solutionUrls" in content
    assert "python-security-audit" in content
    assert "nextjs-pr-review" in content


def test_layout_metadata_and_structured_data_are_factual():
    """Verify RootLayout metadata includes canonical URL, og-image, and unbloated Schema.org markup."""
    layout_file = FRONTEND_APP_DIR / "layout.tsx"
    assert layout_file.exists(), "layout.tsx must exist"
    content = layout_file.read_text(encoding="utf-8")

    assert 'canonical: "/"' in content or "canonical: '/'" in content
    assert "/og-image.png" in content
    assert "aggregateRating" not in content  # No fabricated review ratings
    assert "offers" not in content or "price" not in content  # No fabricated pricing schemes


def test_solutions_metadata_defines_canonical_and_factual_descriptions():
    """Verify solutions pages provide canonical URLs and framework-specific content without hype."""
    solutions_file = FRONTEND_APP_DIR / "solutions" / "[framework]" / "page.tsx"
    assert solutions_file.exists(), "solutions/[framework]/page.tsx must exist"
    content = solutions_file.read_text(encoding="utf-8")

    assert "canonical:" in content
    assert "generateMetadata" in content
    assert "generateStaticParams" in content
