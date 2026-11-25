"""Commands run in a sandbox."""

from __future__ import annotations

import pytest

import fastsandbox
from fastsandbox.models import (
    ExecOutput,
)
from fastsandbox.testing import FakeDaemon


async def test_exec_runs_commands(
    client: fastsandbox.Client, daemon: FakeDaemon, package: fastsandbox.KitPackage
) -> None:
    seen: list[list[str]] = []

    @daemon.on_exec
    def answer(sandbox: str, cmd: list[str]) -> ExecOutput:
        seen.append(cmd)
        return ExecOutput(exit_code=0, stdout="hello\n")

    async with client.create(kit=package) as sandbox:
        output = await sandbox.exec("echo hello", env={"A": "1"}, timeout=30)
        assert output.ok
        assert output.stdout == "hello\n"
        await sandbox.exec(["ls", "-la"])
    assert seen == [["sh", "-c", "echo hello"], ["ls", "-la"]]
    body = daemon.requests_to("POST", "/sandbox/{name}/exec")[0].json()
    assert body["env"] == {"A": "1"}


async def test_failed_commands_raise_when_checked(
    client: fastsandbox.Client, daemon: FakeDaemon, package: fastsandbox.KitPackage
) -> None:
    daemon.on_exec(lambda sandbox, cmd: ExecOutput(exit_code=3, stderr="no\n"))
    async with client.create(kit=package) as sandbox:
        assert (await sandbox.exec("false")).exit_code == 3
        with pytest.raises(fastsandbox.CommandFailedError):
            await sandbox.exec("false", check=True)
