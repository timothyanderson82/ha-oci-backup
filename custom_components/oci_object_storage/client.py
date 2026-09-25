"""S3 client construction for the OCI Object Storage S3 Compatibility API.

This module deliberately has no Home Assistant imports so that the standalone
smoke test in scripts/ can use exactly the same client settings.
"""

import re

from aiobotocore.client import AioBaseClient as S3Client
from aiobotocore.config import AioConfig
from aiobotocore.session import AioSession

NAMESPACE_PATTERN = re.compile(r"^[a-z0-9]+$")
REGION_PATTERN = re.compile(r"^[a-z]+(-[a-z]+)+-\d+$")


def build_endpoint(namespace: str, region: str) -> str:
    """Return the path-style S3 Compatibility API endpoint for a tenancy."""
    return f"https://{namespace}.compat.objectstorage.{region}.oci.customer-oci.com"


def create_client(
    *,
    endpoint_url: str,
    region: str,
    access_key_id: str,
    secret_access_key: str,
) -> S3Client:
    """Return an (unentered) aiobotocore S3 client context for OCI.

    - region_name: OCI verifies SigV4 signatures against the real OCI region;
      the us-east-1 fallback only works for the tenancy's home region.
    - addressing_style=path: the namespace endpoint expects /<bucket>/<key>.
    - checksums "when_required": botocore >= 1.36 sends CRC32 checksums on every
      upload by default, which OCI rejects (it only accepts SHA256 and CRC32C).
    """
    session = AioSession()
    return session.create_client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=AioConfig(
            warm_up_loader_caches=True,
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )
