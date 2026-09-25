"""The OCI Object Storage integration."""

import logging
from typing import cast

from aiobotocore.client import AioBaseClient as S3Client
from botocore.exceptions import (
    ClientError,
    ConnectionError,
    EndpointConnectionError,
    ParamValidationError,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .client import build_endpoint, create_client
from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_NAMESPACE,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
)

type OCIConfigEntry = ConfigEntry[S3Client]


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: OCIConfigEntry) -> bool:
    """Set up OCI Object Storage from a config entry."""

    data = cast(dict, entry.data)
    # pylint: disable-next=unnecessary-dunder-call
    client = await create_client(
        endpoint_url=build_endpoint(data[CONF_NAMESPACE], data[CONF_REGION]),
        region=data[CONF_REGION],
        access_key_id=data[CONF_ACCESS_KEY_ID],
        secret_access_key=data[CONF_SECRET_ACCESS_KEY],
    ).__aenter__()
    try:
        await client.head_bucket(Bucket=data[CONF_BUCKET])
    except ClientError as err:
        await client.__aexit__(None, None, None)
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_credentials",
        ) from err
    except ParamValidationError as err:
        await client.__aexit__(None, None, None)
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_bucket_name",
        ) from err
    except ValueError as err:
        await client.__aexit__(None, None, None)
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_endpoint_url",
        ) from err
    except (ConnectionError, EndpointConnectionError) as err:
        await client.__aexit__(None, None, None)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    entry.runtime_data = client

    def notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(notify_backup_listeners))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OCIConfigEntry) -> bool:
    """Unload a config entry."""
    client = entry.runtime_data
    await client.__aexit__(None, None, None)
    return True
