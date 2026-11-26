"""Cancellation and concurrency of the calls that cross into the native extension."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from fastsandbox import FastSandbox, Sandbox, SandboxTimeoutError
from fastsandbox.models import ExecOutput
from fastsandbox.testing import FakeDaemon, Request, Response


async def test_a_timeout_cancels_a_call_to_the_daemon(
    daemon: FakeDaemon, make_app: Callable[..., FastSandbox]
) -> None:
    started, release = asyncio.Event(), asyncio.Event()

    @daemon.route("POST", "/sandbox/{name}/exec")
    async def hang(request: Request) -> Response:
        started.set()
        await release.wait()
        return Response(200, {"exit_code": 0, "stdout": "", "stderr": ""})

    app = make_app()

    @app.task(timeout="200ms")
    async def stuck(sandbox: Sandbox) -> None:
        await sandbox.exec("sleep 60")

    try:
        with pytest.raises(SandboxTimeoutError):
            await asyncio.wait_for(app.run("stuck"), 10)
    finally:
        release.set()
    assert started.is_set()
    # The awaitable of the extension was cancelled, not left running: the
    # sandbox was deleted after it, through the same extension.
    assert daemon.sandboxes == {}


async def test_concurrent_runs_share_the_extension(
    daemon: FakeDaemon, make_app: Callable[..., FastSandbox]
) -> None:
    @daemon.on_exec
    async def echo_back(sandbox: str, cmd: list[str]) -> ExecOutput:
        # Hand the loop to the other calls before answering.
        await asyncio.sleep(0)
        return ExecOutput(exit_code=0, stdout=cmd[-1])

    app = make_app()

    @app.task
    async def echo(sandbox: Sandbox, word: str) -> list[str]:
        calls = (sandbox.exec(["echo", f"{word}.{index}"]) for index in range(5))
        return [output.stdout for output in await asyncio.gather(*calls)]

    words = [f"w{index}" for index in range(10)]
    async with app, asyncio.TaskGroup() as group:
        runs = [group.create_task(app.run("echo", word=word)) for word in words]
    # Every answer came back to the call that asked for it.
    assert [run.result() for run in runs] == [[f"{w}.{i}" for i in range(5)] for w in words]
    assert len(daemon.requests_to("POST", "/sandbox/{name}/exec")) == 50
    assert daemon.sandboxes == {}
