# Hadron brand identity — version 2

Canonical visual system: `assets/icon.svg`, `assets/logo.svg`, `assets/logo-dark.svg`.
The icon is a four-way convergence mark representing Security, Quality, Testing, and Documentation working toward one consolidated review.

## Design principles

- **Distinctiveness and memorability:** Four connected colored shapes converge on a single dark diamond; never use orbit rings or a generic robot glyph.
- **Scalability:** Use the SVG mark for navigation and responsive UI. At 16 or 32 pixels, use the icon alone rather than the full wordmark.
- **Consistency:** Every logo variation shares one geometry and the same colors; avoid effects, gradients, colored glows, or animations.
- **Clarity and contrast:** Use `logo.svg` on light backgrounds, and `logo-dark.svg` with a light wordmark on dark backgrounds. The central diamond remains charcoal.
- **Accessibility:** Brand images carry a meaningful accessible name when informative. Decorative `HadronIcon` instances are `aria-hidden`. Never rely on color alone to convey software state.
- **Clear space:** Keep at least half of the external node diameter clear around the logo, and avoid stretching or redrawing its proportions.
- **Reproducibility:** All PNGs are exported from checked-in SVG masters without model calls or downloading fonts.

### Color roles

| Role | Hex |
| --- | --- |
| Security / Blue | `#0B69F7` |
| Quality / Red | `#EF4050` |
| Testing / Green | `#08B773` |
| Documentation / Gold | `#F5B800` |
| Core / Wordmark | `#20262F` |
| Dark-surface Wordmark | `#F8FAFC` |

Color-to-role associations describe the brand concept, not a claim that these colors encode live statuses.

### Assets

- `assets/icon.svg`: vector icon master.
- `assets/logo.svg` and `assets/logo-dark.svg`: vector wordmarks.
- `assets/social-card.svg`: 1200×630 social preview master.
- `frontend/public/`: public mirrors, browser icon sizes, Apple touch icon, raster social preview.
- `assets/*.png`: README and repository hosting compatibility exports.

To regenerate all raster artifacts:

```bash
python -m pip install 'cairosvg==2.8.2' 'Pillow==12.3.0'
python scripts/generate_brand_assets.py
python scripts/generate_brand_assets.py --check
```

A GitHub workflow regenerates the PNG assets from their masters on same-repo pull requests. Any logo changes should update the canonical SVG first and verify the derived binaries before merging.
