"""Timeouts and failures of tasks."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from fastsandbox import (
    FastSandbox,
    SandboxTimeoutError,
)
from fastsandbox.testing import FakeDaemon


async def test_timeouts_and_failures_delete_the_sandbox(
    daemon: FakeDaemon, make_app: Callable[..., FastSandbox]
) -> None:

    app = make_app()

    @app.task(timeout="200ms")
    async def slow() -> None:
        await asyncio.sleep(5)

    @app.task
    async def broken() -> None:
        raise RuntimeError("boom")

    with pytest.raises(SandboxTimeoutError) as raised:
        await app.run("slow")
    assert raised.value.after == pytest.approx(0.2)
    with pytest.raises(RuntimeError, match="boom"):
        await app.run("broken")
    assert daemon.sandboxes == {}
