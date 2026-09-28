"""Generate the integration icon: a storage bucket with a backup arrow.

Writes SVG sources to assets/icon/ and the PNGs Home Assistant serves to
custom_components/oci_object_storage/brand/. Needs cairosvg:

    uv run --with cairosvg python scripts/make_icon.py
"""

import math
from pathlib import Path

import cairosvg


def svg(body_dark: str, body_mid: str, rim: str, opening: str, arrow: str) -> str:
    """Return the icon SVG in the given colours."""
    cx, cy, r = 256, 322, 84
    a0, a1 = math.radians(-40), math.radians(225)  # clockwise arc, gap at the top

    def p(a: float) -> tuple[float, float]:
        return cx + r * math.cos(a), cy + r * math.sin(a)

    x0, y0 = p(a0)
    # stop the shaft short so the arrowhead covers its end cleanly
    xe, ye = p(a1 - math.radians(6))
    # arrowhead at a1, pointing along the clockwise tangent
    tx, ty = -math.sin(a1), math.cos(a1)
    bx, by = p(a1)
    nx, ny = math.cos(a1), math.sin(a1)
    w, back, fwd = 34, 10, 44
    head = [
        (bx + tx * fwd, by + ty * fwd),
        (bx - tx * back + nx * w, by - ty * back + ny * w),
        (bx - tx * back - nx * w, by - ty * back - ny * w),
    ]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in head)
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
  <path d="M{x0:.1f} {y0:.1f} A{r} {r} 0 1 1 {xe:.1f} {ye:.1f}" fill="none" stroke="{arrow}" stroke-width="28" stroke-linecap="round"/>
  <polygon points="{pts}" fill="{arrow}" stroke="{arrow}" stroke-width="8" stroke-linejoin="round"/>
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
