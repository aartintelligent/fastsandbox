"""Sessions that keep a sandbox running."""

from __future__ import annotations

import fastsandbox
from fastsandbox.testing import FakeDaemon


async def test_running_holds_a_session(
    client: fastsandbox.Client, daemon: FakeDaemon, package: fastsandbox.KitPackage
) -> None:
    sandbox = await client.create("job-2", kit=package)
    async with sandbox.running():
        assert daemon.requests_to("GET", "/sandbox/{name}/session")
        info = await sandbox.inspect()
        assert info.is_running
    await sandbox.force_delete()
