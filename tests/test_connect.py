"""Connecting to the daemon."""

from __future__ import annotations

from pathlib import Path

import pytest

import fastsandbox
from fastsandbox import (
    DaemonUnavailableError,
)
from fastsandbox.testing import FakeDaemon


async def test_connect_reports_the_health(client: fastsandbox.Client, daemon: FakeDaemon) -> None:
    assert client.health.version == "v0.54.1"
    assert client.health.is_healthy
    assert client.socket_path == daemon.socket_path


async def test_a_missing_daemon_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(DaemonUnavailableError) as raised:
        await fastsandbox.connect(tmp_path / "none.sock")
    assert isinstance(raised.value, ConnectionError)
