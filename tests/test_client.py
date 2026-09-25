"""Verify the wire format the OCI S3 Compatibility API depends on."""

from aiobotocore.session import AioSession

from custom_components.oci_object_storage.client import build_endpoint, create_client

REGION = "af-johannesburg-1"


def test_build_endpoint() -> None:
    """Path-style namespace endpoint on the current OCI domain."""
    assert (
        build_endpoint("axtestns", REGION)
        == "https://axtestns.compat.objectstorage.af-johannesburg-1.oci.customer-oci.com"
    )


async def _capture_put(client, bucket: str) -> dict:
    captured: dict = {}

    def before_send(request, **kwargs):
        captured["url"] = request.url
        captured["headers"] = {
            k.lower(): v.decode() if isinstance(v, bytes) else v
            for k, v in request.headers.items()
        }

    client.meta.events.register("before-send.s3.PutObject", before_send)
    await client.put_object(Bucket=bucket, Key="probe.txt", Body=b"hello")
    return captured


async def test_put_object_request_is_oci_compatible(
    moto_server: str, bucket: str
) -> None:
    """No CRC32 checksum headers, path-style URL, signed for the OCI region."""
    async with create_client(
        endpoint_url=moto_server,
        region=REGION,
        access_key_id="x",
        secret_access_key="x",
    ) as client:
        request = await _capture_put(client, bucket)

    checksum_headers = [
        h
        for h in request["headers"]
        if h.startswith(("x-amz-checksum", "x-amz-sdk-checksum"))
    ]
    assert checksum_headers == []
    assert request["url"] == f"{moto_server}/{bucket}/probe.txt"
    assert f"/{REGION}/s3/aws4_request" in request["headers"]["authorization"]


async def test_default_botocore_would_send_crc32(moto_server: str, bucket: str) -> None:
    """Control: without our config botocore adds the header OCI rejects."""
    async with AioSession().create_client(
        "s3",
        endpoint_url=moto_server,
        region_name=REGION,
        aws_access_key_id="x",
        aws_secret_access_key="x",
    ) as client:
        request = await _capture_put(client, bucket)

    assert "x-amz-checksum-crc32" in request["headers"]
