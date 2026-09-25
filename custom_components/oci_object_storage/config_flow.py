"""Config flow for the OCI Object Storage integration."""

from typing import Any, override

import voluptuous as vol
from botocore.exceptions import (
    ClientError,
    ConnectionError,
    EndpointConnectionError,
    ParamValidationError,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PREFIX
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import NAMESPACE_PATTERN, REGION_PATTERN, build_endpoint, create_client
from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_NAMESPACE,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    DEFAULT_REGION,
    DESCRIPTION_NAMESPACE_DOCS_URL,
    DESCRIPTION_SECRET_KEY_DOCS_URL,
    DOMAIN,
    OCI_REGIONS,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAMESPACE): cv.string,
        vol.Required(CONF_REGION, default=DEFAULT_REGION): SelectSelector(
            SelectSelectorConfig(
                options=OCI_REGIONS,
                custom_value=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(CONF_BUCKET): cv.string,
        vol.Required(CONF_ACCESS_KEY_ID): cv.string,
        vol.Required(CONF_SECRET_ACCESS_KEY): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_PREFIX, default=""): cv.string,
    }
)


def _normalize(user_input: dict[str, Any]) -> dict[str, Any]:
    """Trim user input and drop empty optional values."""
    data = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in user_input.items()
    }
    data[CONF_NAMESPACE] = data[CONF_NAMESPACE].lower()
    data[CONF_REGION] = data[CONF_REGION].lower()
    prefix = data.get(CONF_PREFIX, "").strip("/")
    if prefix:
        data[CONF_PREFIX] = prefix
    else:
        # Do not persist empty optional values
        data.pop(CONF_PREFIX, None)
    return data


async def _validate(data: dict[str, Any]) -> dict[str, str]:
    """Check the bucket is reachable with the given settings; return errors."""
    if not NAMESPACE_PATTERN.match(data[CONF_NAMESPACE]):
        return {CONF_NAMESPACE: "invalid_namespace"}
    if not REGION_PATTERN.match(data[CONF_REGION]):
        return {CONF_REGION: "invalid_region"}

    try:
        async with create_client(
            endpoint_url=build_endpoint(data[CONF_NAMESPACE], data[CONF_REGION]),
            region=data[CONF_REGION],
            access_key_id=data[CONF_ACCESS_KEY_ID],
            secret_access_key=data[CONF_SECRET_ACCESS_KEY],
        ) as client:
            await client.head_bucket(Bucket=data[CONF_BUCKET])
    except ClientError as err:
        # HEAD responses carry no body, so the code is the bare HTTP status
        if err.response.get("Error", {}).get("Code") in ("404", "NoSuchBucket"):
            return {CONF_BUCKET: "bucket_not_found"}
        return {"base": "invalid_credentials"}
    except ParamValidationError:
        return {CONF_BUCKET: "invalid_bucket_name"}
    except ValueError:
        return {CONF_REGION: "invalid_region"}
    except (ConnectionError, EndpointConnectionError):
        return {"base": "cannot_connect"}
    return {}


def _title(data: dict[str, Any]) -> str:
    if prefix := data.get(CONF_PREFIX):
        return f"{data[CONF_BUCKET]} - {prefix}"
    return data[CONF_BUCKET]


def _unique_id(data: dict[str, Any]) -> str:
    return "/".join(
        (
            data[CONF_NAMESPACE],
            data[CONF_REGION],
            data[CONF_BUCKET],
            data.get(CONF_PREFIX, ""),
        )
    )


class OCIObjectStorageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OCI Object Storage."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = _normalize(user_input)
            await self.async_set_unique_id(_unique_id(data))
            self._abort_if_unique_id_configured()

            if not (errors := await _validate(data)):
                return self.async_create_entry(title=_title(data), data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders={
                "namespace_docs_url": DESCRIPTION_NAMESPACE_DOCS_URL,
                "secret_key_docs_url": DESCRIPTION_SECRET_KEY_DOCS_URL,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change settings, e.g. to rotate a Customer Secret Key."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            data = _normalize(user_input)
            await self.async_set_unique_id(_unique_id(data))
            if self.unique_id != entry.unique_id:
                self._abort_if_unique_id_configured()

            if not (errors := await _validate(data)):
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=self.unique_id,
                    title=_title(data),
                    data=data,
                )

        suggested = user_input or {
            **entry.data,
            CONF_SECRET_ACCESS_KEY: "",
            CONF_PREFIX: entry.data.get(CONF_PREFIX, ""),
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, suggested
            ),
            errors=errors,
            description_placeholders={
                "namespace_docs_url": DESCRIPTION_NAMESPACE_DOCS_URL,
                "secret_key_docs_url": DESCRIPTION_SECRET_KEY_DOCS_URL,
            },
        )
