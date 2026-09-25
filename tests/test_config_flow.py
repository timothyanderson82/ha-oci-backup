"""Test the OCI Object Storage config flow."""

from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PREFIX
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.oci_object_storage.const import (
    CONF_NAMESPACE,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    DOMAIN,
)

from .conftest import BUCKET, USER_INPUT


async def _start(hass: HomeAssistant, user_input: dict):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


async def test_create_entry(
    hass: HomeAssistant, bucket: str, s3_endpoint: list
) -> None:
    """Valid settings create an entry; input is normalised."""
    result = await _start(
        hass,
        {
            **USER_INPUT,
            CONF_NAMESPACE: " AXTestNS ",
            CONF_PREFIX: "/homeassistant/",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{BUCKET} - homeassistant"
    assert result["data"][CONF_NAMESPACE] == "axtestns"
    assert result["data"][CONF_PREFIX] == "homeassistant"
    assert ("axtestns", "af-johannesburg-1") in s3_endpoint


async def test_empty_prefix_not_stored(hass: HomeAssistant, bucket: str) -> None:
    """An empty prefix is dropped from the stored data."""
    result = await _start(hass, {**USER_INPUT, CONF_PREFIX: ""})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_PREFIX not in result["data"]
    assert result["title"] == BUCKET


@pytest.mark.parametrize(
    ("override", "errors"),
    [
        ({CONF_NAMESPACE: "bad-ns!"}, {CONF_NAMESPACE: "invalid_namespace"}),
        ({CONF_REGION: "johannesburg"}, {CONF_REGION: "invalid_region"}),
        ({"bucket": "missing-bucket"}, {"bucket": "bucket_not_found"}),
    ],
)
async def test_validation_errors(
    hass: HomeAssistant, bucket: str, override: dict, errors: dict
) -> None:
    """Bad input is reported against the right field."""
    result = await _start(hass, {**USER_INPUT, **override})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors


@pytest.mark.parametrize(
    ("exception", "errors"),
    [
        (
            ClientError({"Error": {"Code": "403"}}, "HeadBucket"),
            {"base": "invalid_credentials"},
        ),
        (
            EndpointConnectionError(endpoint_url="https://x"),
            {"base": "cannot_connect"},
        ),
    ],
)
async def test_connection_errors(
    hass: HomeAssistant, bucket: str, exception: Exception, errors: dict
) -> None:
    """Auth and network failures map to form errors, and the user can retry."""
    with patch(
        "aiobotocore.client.AioBaseClient._make_api_call", side_effect=exception
    ):
        result = await _start(hass, USER_INPUT)
    assert result["errors"] == errors

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The same namespace/region/bucket/prefix cannot be added twice."""
    config_entry.add_to_hass(hass)
    result = await _start(hass, USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_rotates_secret(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Reconfigure updates the entry and reloads it."""
    entry = setup_integration
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_SECRET_ACCESS_KEY: "rotated"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_SECRET_ACCESS_KEY] == "rotated"
