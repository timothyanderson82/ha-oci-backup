"""Constants for the OCI Object Storage integration."""

from collections.abc import Callable
from typing import Final

from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "oci_object_storage"

CONF_NAMESPACE = "namespace"
CONF_REGION = "region"
CONF_BUCKET = "bucket"
CONF_ACCESS_KEY_ID = "access_key_id"
CONF_SECRET_ACCESS_KEY = "secret_access_key"

DEFAULT_REGION: Final = "af-johannesburg-1"

# Commercial OCI regions offered in the dropdown; any other region can be typed in.
OCI_REGIONS: Final = [
    "af-johannesburg-1",
    "ap-chuncheon-1",
    "ap-hyderabad-1",
    "ap-melbourne-1",
    "ap-mumbai-1",
    "ap-osaka-1",
    "ap-seoul-1",
    "ap-singapore-1",
    "ap-sydney-1",
    "ap-tokyo-1",
    "ca-montreal-1",
    "ca-toronto-1",
    "eu-amsterdam-1",
    "eu-frankfurt-1",
    "eu-madrid-1",
    "eu-marseille-1",
    "eu-milan-1",
    "eu-paris-1",
    "eu-stockholm-1",
    "eu-zurich-1",
    "il-jerusalem-1",
    "me-abudhabi-1",
    "me-dubai-1",
    "me-jeddah-1",
    "mx-monterrey-1",
    "mx-queretaro-1",
    "sa-bogota-1",
    "sa-santiago-1",
    "sa-saopaulo-1",
    "sa-valparaiso-1",
    "sa-vinhedo-1",
    "uk-cardiff-1",
    "uk-london-1",
    "us-ashburn-1",
    "us-chicago-1",
    "us-phoenix-1",
    "us-sanjose-1",
]

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)

DESCRIPTION_SECRET_KEY_DOCS_URL: Final = "https://docs.oracle.com/iaas/Content/Identity/Tasks/managingcredentials.htm#create-secret-key"
DESCRIPTION_NAMESPACE_DOCS_URL: Final = "https://docs.oracle.com/en-us/iaas/Content/Object/Tasks/understandingnamespaces.htm"
