"""A shell sandbox, end to end."""

from __future__ import annotations

import asyncio

import fastsandbox
from fastsandbox.models import (
    EventKind,
)


async def test_a_shell_sandbox_end_to_end(client: fastsandbox.Client) -> None:
    events = await client.events.subscribe_live()
    async with client.create(fastsandbox.unique_name("live"), kit="shell") as sandbox:
        async with sandbox.running():
            info = await sandbox.inspect()
            assert info.is_running

            output = await sandbox.exec("echo $GREETING; id -u", env={"GREETING": "hello"})
            assert output.ok
            assert output.stdout.splitlines()[0] == "hello"

            await sandbox.write_file("/tmp/live.txt", "dummy content\n")
            assert await sandbox.read_text("/tmp/live.txt") == "dummy content\n"

            session = await sandbox.attach(["cat"])
            collected = await session.collect("piped through cat\n")
            assert collected.ok
            assert collected.stdout == b"piped through cat\n"

            interactive = await sandbox.attach("read line; echo got:$line; echo err >&2")
            await interactive.write("abc\n")
            await interactive.close_stdin()
            chunks = [chunk async for chunk in interactive]
            assert b"got:abc" in b"".join(c.data for c in chunks if c.stream == "stdout")
            assert b"err" in b"".join(c.data for c in chunks if c.stream == "stderr")
            assert await interactive.wait(10) == 0

            denied = await sandbox.deny_hosts("example.org")
            assert denied.is_applied
            rules = await sandbox.network_rules()
            assert any("example.org" in rule.resources for rule in rules)

            async with await sandbox.ssh_tunnel() as tunnel:
                banner = await asyncio.wait_for(tunnel.read(), 10)
                assert banner.startswith(b"SSH-2.0-")

        lifecycle = []
        async with events:
            async for event in events:
                if event.kind is EventKind.SANDBOX_LIFECYCLE and event.is_about(sandbox.name):
                    lifecycle.append(event.action)
                if lifecycle:
                    break
        assert lifecycle
