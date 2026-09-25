"""Test the OCI Object Storage backup agent end to end against moto."""

import os
from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
from homeassistant.components.backup import AgentBackup, BackupNotFound
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PREFIX
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.oci_object_storage import backup as backup_module
from custom_components.oci_object_storage.backup import async_get_backup_agents

MIB = 2**20


def _agent_backup(backup_id: str, size: int) -> AgentBackup:
    return AgentBackup(
        addons=[],
        backup_id=backup_id,
        date="2026-09-24T04:58:22+02:00",
        database_included=True,
        extra_metadata={},
        folders=[],
        homeassistant_included=True,
        homeassistant_version="2026.9.3",
        name=f"Test {backup_id}",
        protected=True,
        size=size,
    )


def _stream(payload: bytes, chunk: int = 1 * MIB):
    async def open_stream() -> AsyncIterator[bytes]:
        async def gen() -> AsyncIterator[bytes]:
            for i in range(0, len(payload), chunk):
                yield payload[i : i + chunk]

        return gen()

    return open_stream


async def _download(agent, backup_id: str) -> bytes:
    return b"".join([c async for c in await agent.async_download_backup(backup_id)])


async def test_agent_loaded(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """The entry loads and exposes one backup agent named after the bucket."""
    assert setup_integration.state is ConfigEntryState.LOADED
    agents = await async_get_backup_agents(hass)
    assert [a.name for a in agents] == ["ha-backups"]
    assert agents[0].agent_id == f"oci_object_storage.{setup_integration.entry_id}"


@pytest.mark.parametrize(
    ("size", "expected_parts"),
    [(1 * MIB, 0), (12 * MIB, 3)],
    ids=["simple", "multipart"],
)
async def test_upload_list_download_delete(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    size: int,
    expected_parts: int,
) -> None:
    """Round-trip a backup via simple and multipart upload."""
    payload = os.urandom(size)
    progress: list[int] = []
    parts: list[int] = []
    (agent,) = await async_get_backup_agents(hass)
    real_upload_part = agent._client.upload_part

    async def count_parts(**kwargs):
        parts.append(len(kwargs["Body"]))
        return await real_upload_part(**kwargs)

    with (
        patch.object(backup_module, "MULTIPART_MIN_PART_SIZE_BYTES", 5 * MIB),
        patch.object(agent._client, "upload_part", count_parts),
    ):
        await agent.async_upload_backup(
            open_stream=_stream(payload),
            backup=_agent_backup("abc123", size),
            on_progress=lambda bytes_uploaded: progress.append(bytes_uploaded),
        )

    assert len(parts) == expected_parts
    if expected_parts:
        assert parts == [5 * MIB, 5 * MIB, 2 * MIB]
        assert progress[-1] == size

    listed = await agent.async_list_backups()
    assert [b.backup_id for b in listed] == ["abc123"]
    assert await _download(agent, "abc123") == payload

    await agent.async_delete_backup("abc123")
    assert await agent.async_list_backups() == []
    with pytest.raises(BackupNotFound):
        await agent.async_get_backup("abc123")


async def test_prefix_isolates_backups(
    hass: HomeAssistant, config_entry: MockConfigEntry, bucket: str
) -> None:
    """With a prefix, objects are stored under it and others are ignored."""
    from homeassistant.setup import async_setup_component

    config_entry = MockConfigEntry(
        domain=config_entry.domain,
        title=f"{bucket} - homeassistant",
        data={**config_entry.data, CONF_PREFIX: "homeassistant"},
    )
    assert await async_setup_component(hass, "backup", {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    (agent,) = await async_get_backup_agents(hass)
    await agent._client.put_object(
        Bucket=bucket, Key="other.metadata.json", Body=b"{not json"
    )
    await agent.async_upload_backup(
        open_stream=_stream(b"data"),
        backup=_agent_backup("pfx1", 4),
        on_progress=lambda **_: None,
    )

    listing = await agent._client.list_objects_v2(Bucket=bucket)
    keys = sorted(o["Key"] for o in listing["Contents"])
    assert keys == [
        "homeassistant/Test_pfx1_2026-09-24_04.58_22000000.metadata.json",
        "homeassistant/Test_pfx1_2026-09-24_04.58_22000000.tar",
        "other.metadata.json",
    ]
    assert [b.backup_id for b in await agent.async_list_backups()] == ["pfx1"]


async def test_listing_paginates(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Backups beyond the first page of a listing are still found."""
    (agent,) = await async_get_backup_agents(hass)
    for i in range(3):
        await agent.async_upload_backup(
            open_stream=_stream(b"x"),
            backup=_agent_backup(f"id{i}", 1),
            on_progress=lambda **_: None,
        )

    real_paginate = agent._client.get_paginator("list_objects_v2").paginate

    class SmallPages:
        def paginate(self, **kwargs):
            return real_paginate(**kwargs, PaginationConfig={"PageSize": 1})

    with patch.object(agent._client, "get_paginator", return_value=SmallPages()):
        agent._cache_expiration = 0
        found = await agent.async_list_backups()
    assert sorted(b.backup_id for b in found) == ["id0", "id1", "id2"]


async def test_unload(hass: HomeAssistant, setup_integration: MockConfigEntry) -> None:
    """Unloading removes the agent."""
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()
    assert setup_integration.state is ConfigEntryState.NOT_LOADED
    assert await async_get_backup_agents(hass) == []
