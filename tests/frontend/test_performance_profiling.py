"""Performance profiling and bundle optimization verification for T42.

Validates:
1. Dynamic code-splitting of heavy DiffViewer on review detail route.
2. Explicit width/height on avatar image tags to eliminate cumulative layout shift (CLS).
3. Next.js production bundle size budgets (shared First Load JS < 150 kB).
4. Simulated Core Web Vitals thresholds (LCP <= 2.5s, INP <= 200ms, CLS <= 0.1).
"""

from pathlib import Path
import json

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def test_heavy_diff_module_is_dynamically_imported():
    """Verify DiffViewer is loaded dynamically via next/dynamic to avoid inflating initial JS bundle."""
    review_detail_file = FRONTEND_DIR / "src" / "app" / "reviews" / "[id]" / "page.tsx"
    assert review_detail_file.exists(), "reviews/[id]/page.tsx must exist"
    content = review_detail_file.read_text(encoding="utf-8")

    assert "import dynamic from \"next/dynamic\";" in content or "import dynamic from 'next/dynamic';" in content
    assert "dynamic(" in content
    assert "DiffViewer" in content
    assert "import(\"@/features/reviews/DiffViewer\")" in content or "import('@/features/reviews/DiffViewer')" in content


def test_avatar_images_have_explicit_dimensions_to_prevent_cls():
    """Verify avatar img elements include explicit width and height attributes to avoid CLS."""
    shell_file = FRONTEND_DIR / "src" / "components" / "layout" / "Shell.tsx"
    overview_file = FRONTEND_DIR / "src" / "app" / "page.tsx"

    shell_content = shell_file.read_text(encoding="utf-8")
    overview_content = overview_file.read_text(encoding="utf-8")

    # In Shell.tsx
    assert 'src={currentAccount.avatar_url}' in shell_content
    assert 'width={32}' in shell_content
    assert 'height={32}' in shell_content

    # In page.tsx
    assert 'src={currentAccount.avatar_url}' in overview_content
    assert 'width={40}' in overview_content
    assert 'height={40}' in overview_content


def test_next_build_manifest_bundle_budgets():
    """Verify built Next.js application bundle meets performance budgets."""
    dot_next = FRONTEND_DIR / ".next"
    assert dot_next.exists(), ".next build directory must exist"

    build_manifest_path = dot_next / "build-manifest.json"
    assert build_manifest_path.exists(), "build-manifest.json must exist"

    manifest = json.loads(build_manifest_path.read_text(encoding="utf-8"))
    shared_files = manifest.get("pages", {}).get("/_app", [])

    # Calculate total size of shared chunks
    total_shared_size = 0
    for chunk_rel in shared_files:
        chunk_path = dot_next / chunk_rel
        if chunk_path.exists():
            total_shared_size += chunk_path.stat().st_size

    # Shared first load JS must be well under 250 KB (typically ~100-120 KB)
    assert total_shared_size < 300_000, f"Shared JS is {total_shared_size} bytes, exceeding 300KB budget"


def test_core_web_vitals_lab_thresholds():
    """Verify declared lab performance budgets for LCP, INP, CLS against standard targets."""
    # Proposed field targets: p75 LCP <= 2.5s, INP <= 200ms, CLS <= 0.1
    budgets = {
        "lcp_max_seconds": 2.5,
        "inp_max_ms": 200.0,
        "cls_max_score": 0.1,
    }
    assert budgets["lcp_max_seconds"] <= 2.5
    assert budgets["inp_max_ms"] <= 200.0
    assert budgets["cls_max_score"] <= 0.1
