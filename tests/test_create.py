"""Creating sandboxes."""

from __future__ import annotations

import pytest

import fastsandbox
from fastsandbox import (
    ConflictError,
)
from fastsandbox.testing import FakeDaemon


async def test_create_awaited_keeps_the_sandbox(
    client: fastsandbox.Client, daemon: FakeDaemon, package: fastsandbox.KitPackage
) -> None:
    creation = client.create("job-1", kit=package, env={"MODE": "test"}, cpus=2)
    sandbox = await creation
    assert sandbox.name == "job-1"
    assert creation.created is not None
    assert creation.created.status == "running"
    request = daemon.sandboxes["job-1"]["request"]
    assert request["environment"] == {"MODE": "test"}
    assert request["cpus"] == 2
    assert [info.name for info in await client.sandboxes.list()] == ["job-1"]
    with pytest.raises(ConflictError):
        await client.create("job-1", kit=package)


async def test_create_as_context_deletes_the_sandbox(
    client: fastsandbox.Client, daemon: FakeDaemon, package: fastsandbox.KitPackage
) -> None:
    async with client.create(kit=package, workspace="/tmp") as sandbox:
        assert sandbox.name in daemon.sandboxes
        assert daemon.sandboxes[sandbox.name]["request"]["workspace"] == "/tmp"
    assert daemon.sandboxes == {}
