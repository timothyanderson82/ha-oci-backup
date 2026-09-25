#!/usr/bin/env python3
"""Exercise a real OCI bucket with the integration's exact S3 client settings.

Reads connection settings from an ini file (default: ./oci-backup.ini, see
oci-backup.example.ini). Everything is written under a throwaway
_smoke_test/<timestamp>/ folder, which is removed at the end.

    .venv/bin/python scripts/oci_smoke_test.py [config.ini] [--endpoint URL]
"""

import argparse
import asyncio
import configparser
import hashlib
import importlib.util
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIB = 2**20

# Load client.py by path: importing the package would pull in Home Assistant.
_spec = importlib.util.spec_from_file_location(
    "oci_client", ROOT / "custom_components/oci_object_storage/client.py"
)
oci_client = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(oci_client)

REQUIRED = ("namespace", "region", "bucket", "access_key_id", "secret_access_key")


def load_config(path: Path) -> dict[str, str]:
    parser = configparser.ConfigParser()
    if not parser.read(path):
        sys.exit(f"Config file not found: {path} (copy oci-backup.example.ini)")
    cfg = dict(parser["oci"])
    if missing := [k for k in REQUIRED if not cfg.get(k)]:
        sys.exit(f"Missing settings in {path}: {', '.join(missing)}")
    return cfg


async def run(cfg: dict[str, str], endpoint: str) -> bool:
    bucket = cfg["bucket"]
    base = "/".join(
        p
        for p in (cfg.get("prefix", "").strip("/"), f"_smoke_test/{int(time.time())}")
        if p
    )
    ok = True

    async def step(name, coro):
        nonlocal ok
        started = time.monotonic()
        try:
            detail = await coro
        except Exception as err:  # noqa: BLE001
            ok = False
            print(f"  FAIL  {name}: {type(err).__name__}: {err}")
            return False
        print(
            f"  ok    {name} ({time.monotonic() - started:.1f}s){f' - {detail}' if detail else ''}"
        )
        return True

    async with oci_client.create_client(
        endpoint_url=endpoint,
        region=cfg["region"],
        access_key_id=cfg["access_key_id"],
        secret_access_key=cfg["secret_access_key"],
    ) as client:

        async def head():
            await client.head_bucket(Bucket=bucket)

        async def simple():
            body = os.urandom(64 * 1024)
            await client.put_object(Bucket=bucket, Key=f"{base}/small.bin", Body=body)
            got = await (
                await client.get_object(Bucket=bucket, Key=f"{base}/small.bin")
            )["Body"].read()
            assert got == body, "downloaded content differs"
            return "64 KiB round-trip"

        async def multipart():
            key = f"{base}/multipart.bin"
            parts_data = [os.urandom(5 * MIB), os.urandom(5 * MIB), os.urandom(1 * MIB)]
            upload = await client.create_multipart_upload(Bucket=bucket, Key=key)
            parts = []
            for number, data in enumerate(parts_data, start=1):
                part = await client.upload_part(
                    Bucket=bucket,
                    Key=key,
                    PartNumber=number,
                    UploadId=upload["UploadId"],
                    Body=data,
                )
                parts.append({"PartNumber": number, "ETag": part["ETag"]})
            await client.complete_multipart_upload(
                Bucket=bucket,
                Key=key,
                UploadId=upload["UploadId"],
                MultipartUpload={"Parts": parts},
            )
            response = await client.get_object(Bucket=bucket, Key=key)
            digest = hashlib.sha256()
            async for chunk in response["Body"].iter_chunks():
                digest.update(chunk)
            assert digest.digest() == hashlib.sha256(b"".join(parts_data)).digest(), (
                "downloaded content differs"
            )
            return "3 parts, 11 MiB round-trip"

        async def abort():
            upload = await client.create_multipart_upload(
                Bucket=bucket, Key=f"{base}/aborted.bin"
            )
            await client.abort_multipart_upload(
                Bucket=bucket, Key=f"{base}/aborted.bin", UploadId=upload["UploadId"]
            )

        async def list_keys():
            keys = []
            async for page in client.get_paginator("list_objects_v2").paginate(
                Bucket=bucket, Prefix=f"{base}/"
            ):
                keys.extend(o["Key"] for o in page.get("Contents", []))
            return keys

        async def listing():
            keys = await list_keys()
            expected = {f"{base}/small.bin", f"{base}/multipart.bin"}
            assert set(keys) == expected, f"unexpected listing: {keys}"
            return f"{len(keys)} objects"

        async def cleanup():
            for key in await list_keys():
                await client.delete_object(Bucket=bucket, Key=key)
            assert await list_keys() == [], "objects left behind"

        print(f"Endpoint: {endpoint}\nBucket:   {bucket}\nTest dir: {base}/")
        if await step("head bucket (credentials, namespace, region)", head()):
            await step("simple upload + download", simple())
            await step("multipart upload + download", multipart())
            await step("abort multipart upload", abort())
            await step("list objects", listing())
            await step("delete objects", cleanup())
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("config", nargs="?", default=ROOT / "oci-backup.ini", type=Path)
    parser.add_argument("--endpoint", help="override the endpoint (testing only)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    endpoint = args.endpoint or oci_client.build_endpoint(
        cfg["namespace"], cfg["region"]
    )
    passed = asyncio.run(run(cfg, endpoint))
    print("PASSED" if passed else "FAILED")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
