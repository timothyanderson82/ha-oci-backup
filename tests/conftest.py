"""Fixtures for OCI Object Storage tests, backed by a local moto S3 server."""

import socket
import subprocess
import sys
import time
from collections.abc import Generator
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.oci_object_storage.const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_NAMESPACE,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    DOMAIN,
)

MOTO_PORT = 5055
MOTO_URL = f"http://127.0.0.1:{MOTO_PORT}"
BUCKET = "ha-backups"

USER_INPUT = {
    CONF_NAMESPACE: "axtestns",
    CONF_REGION: "af-johannesburg-1",
    CONF_BUCKET: BUCKET,
    CONF_ACCESS_KEY_ID: "test-access",
    CONF_SECRET_ACCESS_KEY: "test-secret",
}


_moto_process: subprocess.Popen | None = None


def pytest_sessionstart(session: pytest.Session) -> None:
    """Start moto in a subprocess.

    The HA test harness blocks socket creation inside tests, so the server
    cannot run in a thread of the test process.
    """
    global _moto_process  # noqa: PLW0603
    _moto_process = subprocess.Popen(
        [sys.executable, "-m", "moto.server", "-H", "127.0.0.1", "-p", str(MOTO_PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            socket.create_connection(("127.0.0.1", MOTO_PORT), timeout=1).close()
            return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError("moto server did not start")


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Stop the moto subprocess."""
    if _moto_process:
        _moto_process.terminate()
        _moto_process.wait()


@pytest.fixture
def moto_server() -> str:
    """Return the URL of the moto S3 server."""
    return MOTO_URL


@pytest.fixture(autouse=True)
def allow_moto_sockets(socket_enabled: None) -> None:
    """Allow real TCP connections; only the local moto server is ever reached."""


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow loading custom_components/."""


@pytest.fixture(autouse=True)
def s3_endpoint(moto_server: str) -> Generator[list[tuple[str, str]]]:
    """Point the integration at moto and record every endpoint it builds."""
    built: list[tuple[str, str]] = []

    def fake_endpoint(namespace: str, region: str) -> str:
        built.append((namespace, region))
        return moto_server

    with (
        patch("custom_components.oci_object_storage.build_endpoint", fake_endpoint),
        patch(
            "custom_components.oci_object_storage.config_flow.build_endpoint",
            fake_endpoint,
        ),
    ):
        yield built


@pytest.fixture
async def bucket(moto_server: str) -> str:
    """Create an empty test bucket (recreated for every test)."""
    from aiobotocore.session import AioSession

    async with AioSession().create_client(
        "s3",
        endpoint_url=moto_server,
        region_name="us-east-1",
        aws_access_key_id="x",
        aws_secret_access_key="x",
    ) as client:
        try:
            listing = await client.list_objects_v2(Bucket=BUCKET)
            for obj in listing.get("Contents", []):
                await client.delete_object(Bucket=BUCKET, Key=obj["Key"])
        except client.exceptions.NoSuchBucket:
            await client.create_bucket(Bucket=BUCKET)
    return BUCKET


@pytest.fixture
def config_entry(bucket: str) -> MockConfigEntry:
    """Return a config entry for the test bucket."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=BUCKET,
        unique_id="axtestns/af-johannesburg-1/ha-backups/",
        data=USER_INPUT,
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up backup and the integration."""
    assert await async_setup_component(hass, "backup", {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
