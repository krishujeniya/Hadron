#!/usr/bin/env python3
"""Deterministic Hadron brand PNG exports from canonical SVG masters.

Install: pip install cairosvg pillow
Run: python scripts/generate_brand_assets.py
Checks: python scripts/generate_brand_assets.py --check

No remote downloads, credentials, model calls, or data access are needed.
"""
from __future__ import annotations

import argparse
import io
from pathlib import Path

import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
PUBLIC = ROOT / "frontend" / "public"

# Export names and exact dimensions are part of the app and CI contract.
EXPORTS: tuple[tuple[str, tuple[int, int], tuple[str, ...]], ...] = (
    ("icon.svg", (16, 16), ("frontend/public/favicon-16x16.png",)),
    ("icon.svg", (32, 32), ("frontend/public/favicon-32x32.png",)),
    ("icon.svg", (180, 180), ("frontend/public/apple-touch-icon.png",)),
    ("icon.svg", (192, 192), ("frontend/public/icon-192.png",)),
    ("icon.svg", (512, 512), ("frontend/public/icon-512.png", "assets/icon.png")),
    ("logo.svg", (900, 256), ("frontend/public/logo.png", "assets/logo.png")),
    ("social-card.svg", (1200, 630), ("frontend/public/og-image.png", "assets/og-image.png")),
)


def source_for(name: str) -> Path:
    return ASSETS / name


def render(source: Path, size: tuple[int, int]) -> bytes:
    width, height = size
    # Supersample only tiny icons; this keeps AA stable at favicon resolution.
    factor = 4 if width <= 32 else 1
    png = cairosvg.svg2png(
        bytestring=source.read_bytes(),
        output_width=width * factor,
        output_height=height * factor,
    )
    with Image.open(io.BytesIO(png)) as loaded:
        image = loaded.convert("RGBA")
        if factor > 1:
            image = image.resize(size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True, compress_level=9)
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if checked-in PNGs are stale")
    args = parser.parse_args()
    stale: list[str] = []
    for source_name, size, destinations in EXPORTS:
        data = render(source_for(source_name), size)
        with Image.open(io.BytesIO(data)) as image:
            assert image.size == size, (source_name, image.size, size)
        for name in destinations:
            path = ROOT / name
            if args.check:
                if not path.exists() or path.read_bytes() != data:
                    stale.append(name)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                print(f"{name}: {size[0]}x{size[1]}, {len(data)} bytes")
    if stale:
        for name in stale:
            print(f"Stale brand export: {name}")
        return 1
    print("Hadron brand assets verified" if args.check else "Hadron brand PNG exports generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
