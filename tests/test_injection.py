"""Parameters injected by annotation."""

from __future__ import annotations

from collections.abc import Callable

from fastsandbox import (
    Client,
    Context,
    FastSandbox,
    Sandbox,
)
from fastsandbox.testing import FakeDaemon


async def test_injection_by_annotation(
    daemon: FakeDaemon, make_app: Callable[..., FastSandbox]
) -> None:
    app = make_app()

    @app.task
    async def kinds(sandbox: Sandbox, client: Client, ctx: Context) -> list[str]:
        assert sandbox is ctx.sandbox
        assert client is ctx.client
        return [type(sandbox).__name__, type(client).__name__]

    assert await kinds() == ["Sandbox", "Client"]
