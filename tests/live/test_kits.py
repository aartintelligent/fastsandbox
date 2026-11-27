"""Kits forged without the `sbx` CLI, against the real daemon."""

from __future__ import annotations

import json
from pathlib import Path

import fastsandbox
from fastsandbox import Kit, KitForge

MIXIN = {
    "schemaVersion": "3",
    "kind": "mixin",
    "displayName": "Live tools",
    "capabilities": [
        {
            "type": "com.docker.sandbox/lifecycle@1",
            "config": {
                "install": [{"command": "echo installed > /tmp/live-tools", "user": "agent"}]
            },
        }
    ],
}


async def test_a_forged_kit_and_its_mixin_create_a_sandbox(
    client: fastsandbox.Client, tmp_path: Path
) -> None:
    tools = tmp_path / "live-tools"
    tools.mkdir()
    (tools / "spec.yaml").write_text(json.dumps(MIXIN))
    package = await KitForge(client).forge(Kit(base="shell", mixins=(str(tools),)))
    assert package.dir is None
    assert package.compiled_api == client.health.api_version
    async with (
        client.create(fastsandbox.unique_name("live-forge"), kit=package) as sandbox,
        sandbox.running(),
    ):
        assert await sandbox.read_text("/tmp/live-tools") == "installed\n"


async def test_an_agent_kit_is_forged_with_its_agent(client: fastsandbox.Client) -> None:
    package = await client.package("claude")
    assert package.agent is not None
    assert package.agent.name == "claude"
    assert "api.anthropic.com" in package.agent.hosts()
