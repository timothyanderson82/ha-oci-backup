"""Test the brand icons shipped with the integration."""

from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from PIL import Image

from custom_components.oci_object_storage.const import DOMAIN

EXPECTED_SIZES = {
    "icon.png": 256,
    "icon@2x.png": 512,
    "dark_icon.png": 256,
    "dark_icon@2x.png": 512,
}


async def test_brand_icons(hass: HomeAssistant) -> None:
    """Home Assistant picks up the local brand folder; icons are square PNGs."""
    integration = await async_get_integration(hass, DOMAIN)
    assert integration.has_branding

    brand_dir = Path(integration.file_path) / "brand"
    assert sorted(p.name for p in brand_dir.iterdir()) == sorted(EXPECTED_SIZES)
    for name, size in EXPECTED_SIZES.items():
        with Image.open(brand_dir / name) as image:
            assert image.format == "PNG"
            assert image.size == (size, size)
            assert image.mode == "RGBA"
