#!/usr/bin/env python3
"""
scripts/generate_pngs.py

Generates pixel-perfect PNG assets from SVGs using headless Google Chrome.
Produces:
  - icon-512.png (512x512)
  - icon-192.png (192x192)
  - apple-touch-icon.png (180x180)
  - favicon-32x32.png (32x32)
  - favicon-16x16.png (16x16)
  - logo.png (1320x288, @3x retina brand mark)
  - og-image.png (1200x630 social card)
"""

import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = ROOT / "frontend" / "public"
ASSETS_DIR = ROOT / "assets"

PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

FAVICON_SVG = (PUBLIC_DIR / "favicon.svg").read_text()
LOGO_SVG = (PUBLIC_DIR / "logo.svg").read_text()

OG_IMAGE_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    width: 1200px;
    height: 630px;
    overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif;
    background: #0B0D12;
    color: #FFFFFF;
    position: relative;
  }
  .bg-glow-1 {
    position: absolute;
    top: 50%;
    left: 20%;
    transform: translate(-50%, -50%);
    width: 600px;
    height: 600px;
    background: radial-gradient(circle, rgba(56, 189, 248, 0.15) 0%, rgba(99, 102, 241, 0.05) 50%, transparent 70%);
    filter: blur(60px);
    pointer-events: none;
  }
  .bg-glow-2 {
    position: absolute;
    bottom: -100px;
    right: -100px;
    width: 500px;
    height: 500px;
    background: radial-gradient(circle, rgba(168, 85, 247, 0.12) 0%, transparent 70%);
    filter: blur(80px);
    pointer-events: none;
  }
  .container {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    padding: 0 90px;
    gap: 70px;
    position: relative;
    z-index: 2;
  }
  .icon-wrap {
    width: 320px;
    height: 320px;
    flex-shrink: 0;
  }
  .icon-wrap svg {
    width: 100%;
    height: 100%;
    filter: drop-shadow(0 20px 40px rgba(99, 102, 241, 0.35));
  }
  .text-wrap {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-radius: 9999px;
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.35);
    color: #818CF8;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    font-family: monospace;
    margin-bottom: 20px;
    width: fit-content;
  }
  .badge-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #38BDF8;
    box-shadow: 0 0 10px #38BDF8;
  }
  h1 {
    font-size: 64px;
    font-weight: 900;
    letter-spacing: 0.12em;
    line-height: 1.05;
    background: linear-gradient(135deg, #FFFFFF 0%, #E2E8F0 50%, #94A3B8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-family: system-ui, -apple-system, sans-serif;
    margin-bottom: 12px;
  }
  .tagline {
    font-size: 22px;
    font-weight: 600;
    color: #38BDF8;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-family: monospace;
    margin-bottom: 18px;
  }
  .desc {
    font-size: 18px;
    line-height: 1.5;
    color: #94A3B8;
    margin-bottom: 30px;
    max-width: 580px;
  }
  .agents-grid {
    display: flex;
    gap: 12px;
  }
  .agent-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    border-radius: 8px;
    background: #12151D;
    border: 1px solid #1F2430;
    font-size: 13px;
    font-family: monospace;
    font-weight: 600;
  }
  .dot-sec { width: 8px; height: 8px; border-radius: 50%; background: #38BDF8; }
  .dot-qua { width: 8px; height: 8px; border-radius: 50%; background: #6366F1; }
  .dot-tes { width: 8px; height: 8px; border-radius: 50%; background: #10B981; }
  .dot-doc { width: 8px; height: 8px; border-radius: 50%; background: #A855F7; }
</style>
</head>
<body>
  <div class="bg-glow-1"></div>
  <div class="bg-glow-2"></div>
  <div class="container">
    <div class="icon-wrap">
      __ICON_SVG__
    </div>
    <div class="text-wrap">
      <div class="badge">
        <span class="badge-dot"></span>
        Multi-Agent PR Review
      </div>
      <h1>HADRON</h1>
      <div class="tagline">Autonomous Code Intelligence</div>
      <p class="desc">
        Parallel specialist sub-agents reasoning over pull requests — detecting vulnerabilities, enforcing architecture, and verifying coverage before merge.
      </p>
      <div class="agents-grid">
        <div class="agent-pill"><span class="dot-sec"></span>Security</div>
        <div class="agent-pill"><span class="dot-qua"></span>Quality</div>
        <div class="agent-pill"><span class="dot-tes"></span>Tests</div>
        <div class="agent-pill"><span class="dot-doc"></span>Docs</div>
      </div>
    </div>
  </div>
</body>
</html>
""".replace("__ICON_SVG__", FAVICON_SVG)

def render_html_to_png(html_content: str, output_path: Path, width: int, height: int):
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as tf:
        tf.write(html_content)
        temp_path = tf.name

    try:
        cmd = [
            "google-chrome",
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--screenshot={output_path}",
            f"--window-size={width},{height}",
            "--default-background-color=00000000",
            f"file://{temp_path}",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"Rendered: {output_path.name} ({width}x{height})")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def make_svg_html(svg_string: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ width: 100%; height: 100%; overflow: hidden; background: transparent; }}
  svg {{ width: 100%; height: 100%; display: block; }}
</style>
</head>
<body>
{svg_string}
</body>
</html>"""

def main():
    print("Generating Hadron Production PNG Assets...")
    svg_html = make_svg_html(FAVICON_SVG)
    logo_html = make_svg_html(LOGO_SVG)

    # 1. Square App Icons
    icon_targets = [
        ("icon-512.png", 512, 512),
        ("icon-192.png", 192, 192),
        ("apple-touch-icon.png", 180, 180),
        ("favicon-32x32.png", 32, 32),
        ("favicon-16x16.png", 16, 16),
    ]

    for fname, w, h in icon_targets:
        out_public = PUBLIC_DIR / fname
        render_html_to_png(svg_html, out_public, w, h)

    # 2. Horizontal Brand Logo (1320x288 @3x high DPI)
    render_html_to_png(logo_html, PUBLIC_DIR / "logo.png", 1320, 288)

    # 3. Social / OpenGraph Card (1200x630)
    render_html_to_png(OG_IMAGE_HTML, PUBLIC_DIR / "og-image.png", 1200, 630)

    # 4. Copy high-res versions to assets/ for README and repository root
    import shutil
    shutil.copyfile(PUBLIC_DIR / "icon-512.png", ASSETS_DIR / "icon.png")
    shutil.copyfile(PUBLIC_DIR / "logo.png", ASSETS_DIR / "logo.png")
    shutil.copyfile(PUBLIC_DIR / "og-image.png", ASSETS_DIR / "og-image.png")
    print(f"Copied master assets to {ASSETS_DIR}")
    print("PNG Generation complete!")

if __name__ == "__main__":
    main()
