"""Generate the integration icon: a storage bucket holding three objects.

Writes SVG sources to assets/icon/ and the PNGs Home Assistant serves to
custom_components/oci_object_storage/brand/. Needs cairosvg:

    uv run --with cairosvg python scripts/make_icon.py
"""

import math
from pathlib import Path

import cairosvg


def _polygon(cx: float, cy: float, r: float, sides: int, start_deg: float) -> str:
    """Return SVG points for a regular polygon."""
    pts = []
    for i in range(sides):
        a = math.radians(start_deg + i * 360 / sides)
        pts.append(f"{cx + r * math.cos(a):.1f},{cy + r * math.sin(a):.1f}")
    return " ".join(pts)


def svg(body_dark: str, body_mid: str, rim: str, opening: str, shapes: str) -> str:
    """Return the icon SVG in the given colours.

    The three solid shapes stand for the objects stored in the bucket.
    """
    triangle = _polygon(186, 302, 56, 3, -90)  # point up
    hexagon = _polygon(328, 296, 50, 6, 0)  # flat top
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <linearGradient id="body" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{body_dark}"/>
      <stop offset="0.45" stop-color="{body_mid}"/>
      <stop offset="1" stop-color="{body_dark}"/>
    </linearGradient>
  </defs>
  <path d="M60 128 L116 452 A140 42 0 0 0 396 452 L452 128 Z" fill="url(#body)"/>
  <ellipse cx="256" cy="128" rx="196" ry="60" fill="{rim}"/>
  <ellipse cx="256" cy="132" rx="170" ry="45" fill="{opening}"/>
  <g fill="{shapes}" stroke="{shapes}" stroke-width="14" stroke-linejoin="round">
    <polygon points="{triangle}"/>
    <polygon points="{hexagon}"/>
    <circle cx="256" cy="402" r="40"/>
  </g>
</svg>
'''


VARIANTS = {
    # Oracle-style charcoal bucket with a red rim (light UI)
    "icon": ("#2E2A27", "#4A4540", "#C74634", "#1C1917", "#FFFFFF"),
    # lighter body so the bucket stays visible on dark UI
    "dark_icon": ("#6A625B", "#8C837B", "#E0584A", "#3A3531", "#FFFFFF"),
}

ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = ROOT / "assets/icon"
BRAND_DIR = ROOT / "custom_components/oci_object_storage/brand"

if __name__ == "__main__":
    SVG_DIR.mkdir(parents=True, exist_ok=True)
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    for name, colours in VARIANTS.items():
        source = svg(*colours)
        (SVG_DIR / f"{name}.svg").write_text(source)
        # Home Assistant brand sizes: 256x256 and 512x512 (@2x)
        for suffix, size in (("", 256), ("@2x", 512)):
            cairosvg.svg2png(
                bytestring=source.encode(),
                write_to=str(BRAND_DIR / f"{name}{suffix}.png"),
                output_width=size,
                output_height=size,
            )
