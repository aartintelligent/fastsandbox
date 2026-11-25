"""Tests of the probe against the fake daemon of fastsandbox.

The fake daemon does not run commands: `on_exec` decides what they print, here
from the command line it receives.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from probe import Probe, probe

import fastsandbox
from fastsandbox import Kit
from fastsandbox.models import ExecOutput
from fastsandbox.testing import FakeDaemon, fake_package


@pytest.fixture
async def daemon(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[FakeDaemon]:
    """A fake daemon the client reaches as it would the real one.

    `DOCKER_SANDBOXES_API` names its socket, and the kit cache holds a package
    of the `shell` kit, so that the code under test needs no change and no
    `sbx` CLI.
    """
    async with FakeDaemon() as fake:
        kits = tmp_path / "kits"
        fake_package(kits / Kit(base="shell").cache_key)
        monkeypatch.setenv(fastsandbox.SOCKET_ENV, str(fake.socket_path))
        monkeypatch.setenv("FASTSANDBOX_KIT_CACHE", str(kits))
        yield fake


def answer(sandbox: str, command: list[str]) -> ExecOutput:
    """What the commands of the probe print in a sandbox."""
    if "uname" in " ".join(command):
        return ExecOutput(exit_code=0, stdout="Linux x86_64\n")
    return ExecOutput(exit_code=0, stdout="Python 3.14.0\n")


async def test_probe(daemon: FakeDaemon) -> None:
    daemon.on_exec(answer)
    client = await fastsandbox.connect()
    assert await probe(client) == Probe(system="Linux x86_64", python="Python 3.14.0")
    assert daemon.sandboxes == {}
