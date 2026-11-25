"""Synchronous tasks."""

from __future__ import annotations

from collections.abc import Callable

from fastsandbox import (
    Context,
    FastSandbox,
)
from fastsandbox.models import (
    ExecOutput,
)
from fastsandbox.testing import FakeDaemon


async def test_sync_tasks_run_in_a_thread(
    daemon: FakeDaemon, make_app: Callable[..., FastSandbox]
) -> None:
    app = make_app()
    daemon.on_exec(lambda sandbox, cmd: ExecOutput(exit_code=0, stdout="from sync\n"))

    @app.task
    def blocking(ctx: Context) -> str:
        return ctx.wait(ctx.sandbox.exec("echo")).stdout.strip()

    assert await app.run("blocking") == "from sync"
