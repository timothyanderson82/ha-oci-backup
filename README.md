<img src="custom_components/oci_object_storage/brand/icon.png" alt="" width="96" align="right">

# OCI Object Storage backup location for Home Assistant

A custom integration that adds an Oracle Cloud (OCI) Object Storage bucket as a
Home Assistant **backup location**, using OCI's S3 Compatibility API.

Built from HA's own `cloudflare_r2` backup integration (HA 2026.9.3), changed to
work with OCI:

- **Region-aware SigV4 signing:** requests are signed for the real OCI region.
  OCI rejects signatures for other regions, and the `us-east-1` fallback only
  works for the tenancy's home region.
- **Checksums set to `when_required`:** botocore ≥ 1.36 adds CRC32 checksums to
  every upload, and OCI accepts only SHA256 and CRC32C.
- **Path-style addressing** against
  `https://<namespace>.compat.objectstorage.<region>.oci.customer-oci.com`.
- **Paginated bucket listing**, a **reconfigure flow** for rotating keys, and an
  S3 client that is closed if setup fails.

All connection details are set on the setup form: namespace, region, bucket,
access key, secret key and an optional folder prefix.

## 1. OCI setup

1. **Bucket:** in the console, create a private bucket (e.g. `ha-backups`) in
   your region, in your chosen compartment. **Versioning must be off.**
   With versioning on, a backup that HA deletes under its retention setting
   isn't removed. OCI keeps it as a hidden previous version. HA can't see
   those versions, so storage (and cost) grows with every backup ever made
   while the bucket looks like it holds only the retained ones. One bucket
   reached 56 GB with only 3 GB of live backups, which put it over the
   20 GB Always Free allowance.

   If versioning is already on, OCI won't set it back to `Disabled`, only to
   `Suspended`. Suspending stops new versions being kept, but the existing
   ones stay until you delete them:
   ```bash
   oci os bucket update -bn ha-backups --versioning Suspended

   # List every version except the newest version of each live object
   # (this includes delete markers), as "<name> <version-id>":
   oci os object list-object-versions -bn ha-backups --all --output json | python3 -c '
   import json, sys
   versions = json.load(sys.stdin)["data"]
   latest = {}
   for v in versions:
       if v["name"] not in latest or v["time-modified"] > latest[v["name"]]["time-modified"]:
           latest[v["name"]] = v
   for v in versions:
       if not (latest[v["name"]] is v and not v["is-delete-marker"]):
           print(v["name"], v["version-id"])
   ' > old-versions.txt

   # Check the list, then delete:
   while read -r name version; do
     oci os object delete -bn ha-backups --name "$name" --version-id "$version" --force
   done < old-versions.txt
   ```
2. **User and group:** create a user `ha-backup` in a group `ha-backup`, with this policy:
   ```
   Allow group ha-backup to read buckets in compartment <compartment>
   Allow group ha-backup to manage objects in compartment <compartment> where target.bucket.name='ha-backups'
   ```
3. **Key:** for that user, go to Profile → User settings → **Customer secret keys** →
   Generate. Copy the secret straight away; it is shown only once.
4. **Namespace:** run `oci os ns get`, or look on the bucket details page.

## 2. Smoke test against the real bucket

```bash
cp oci-backup.example.ini oci-backup.ini   # git-ignored; fill in the values
.venv/bin/python scripts/oci_smoke_test.py
```

This uses the integration's exact client settings (`client.py`). It checks
credentials, simple and multipart uploads with content verification, aborting a
multipart upload, listing and deletion, all under a temporary `_smoke_test/`
folder that it then removes.

## 3. Install

### With HACS (recommended)

1. HACS → ⋮ → **Custom repositories** → add
   `https://github.com/timothyanderson82/ha-oci-backup`, type **Integration**.
2. Find **OCI Object Storage** in HACS → **Download**, then restart Home Assistant.
3. Settings → Devices & services → Add integration → **OCI Object Storage**.

HACS installs the latest GitHub release and shows new releases as updates in
Settings → Updates.

### Manually

Copy `custom_components/oci_object_storage/` into your Home Assistant config
directory's `custom_components/`, then restart Home Assistant.

## 4. Configure backups

- Settings → System → Backups → **Backup settings** → Locations: enable the
  bucket.
- Open the bucket's location → **Backup retention** to choose how many copies
  to keep, e.g. Custom → **1 copy** for a single off-site copy.
  Storage peaks at about 2 copies while the new backup uploads, before the old
  one is deleted.

## Development

```bash
uv venv .venv --python 3.14
uv pip install --python .venv "homeassistant==2026.9.3" \
  pytest-homeassistant-custom-component "moto[server]" aiobotocore==3.7.0
.venv/bin/pytest
```

Tests run the integration inside HA's test harness against a local moto S3
server. They include checks that uploads carry no checksum headers, use
path-style URLs and are signed for the OCI region.

## Releasing

1. Bump `version` in `custom_components/oci_object_storage/manifest.json` and commit.
2. Tag and publish a release; the tag must match the manifest version:
   ```bash
   git tag v0.2.0 && git push origin main v0.2.0
   gh release create v0.2.0 --generate-notes
   ```
3. Home Assistant shows the update through HACS.

CI (`.github/workflows/validate.yml`) runs hassfest, HACS validation and the
tests on every push and pull request.

## Requirements

Built and unit-tested against Home Assistant 2026.9.3 (Python 3.14, aiobotocore 3.7.0).

## Icon

The icon lives in `custom_components/oci_object_storage/brand/`, which Home
Assistant serves for custom integrations. It is original artwork, generated by
`scripts/make_icon.py` from the SVG sources in `assets/icon/`:

```bash
uv run --no-project --with cairosvg python scripts/make_icon.py
```

## Licence

MIT, see [LICENSE](LICENSE), including the icon. Parts of the integration are adapted from Home
Assistant core's `cloudflare_r2` integration (Apache-2.0), see [NOTICE](NOTICE).
