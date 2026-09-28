"""Generate the integration icon: a line-art storage bucket.

Writes SVG sources to assets/icon/ and the PNGs Home Assistant serves to
custom_components/oci_object_storage/brand/. Needs cairosvg:

    uv run --with cairosvg python scripts/make_icon.py
"""

from pathlib import Path

import cairosvg


def svg(colour: str) -> str:
    """Return the icon SVG: a line-art bucket with a handle, in one colour."""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <g fill="none" stroke="{colour}" stroke-width="34" stroke-linejoin="round" stroke-linecap="round">
    <path d="M162 176 V132 Q162 88 206 88 H306 Q350 88 350 132 V176"/>
    <path d="M66 190 H446 L394 474 H118 Z"/>
  </g>
  <rect x="190" y="52" width="132" height="64" rx="26" fill="{colour}"/>
</svg>
'''


VARIANTS = {
    # Oracle red-orange for light UI
    "icon": "#C74634",
    # brighter shade so the outline stays clear on dark UI
    "dark_icon": "#E2664F",
}

ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = ROOT / "assets/icon"
BRAND_DIR = ROOT / "custom_components/oci_object_storage/brand"

if __name__ == "__main__":
    SVG_DIR.mkdir(parents=True, exist_ok=True)
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    for name, colour in VARIANTS.items():
        source = svg(colour)
        (SVG_DIR / f"{name}.svg").write_text(source)
        # Home Assistant brand sizes: 256x256 and 512x512 (@2x)
        for suffix, size in (("", 256), ("@2x", 512)):
            cairosvg.svg2png(
                bytestring=source.encode(),
                write_to=str(BRAND_DIR / f"{name}{suffix}.png"),
                output_width=size,
                output_height=size,
            )
