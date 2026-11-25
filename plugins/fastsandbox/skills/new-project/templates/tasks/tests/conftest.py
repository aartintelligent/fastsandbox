"""A fake daemon for the tests: no Docker Sandboxes, no sandbox, no network."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

import fastsandbox
from fastsandbox import Kit
from fastsandbox.testing import FakeDaemon, fake_package


@pytest.fixture
async def daemon(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[FakeDaemon]:
    """A fake daemon the application reaches as it would the real one.

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
