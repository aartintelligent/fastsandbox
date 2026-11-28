"""Cancellation and concurrency of the calls that cross into the native extension."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import pytest

from fastsandbox import DaemonUnavailableError, FastSandbox, Sandbox, SandboxTimeoutError
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


@pytest.mark.parametrize("bound", ["application", "task"])
def test_the_bounds_hold_in_one_event_loop_after_another(bound: str, tmp_path: Path) -> None:
    # No daemon: each run waits for its connection while it holds its slot.
    app = FastSandbox(
        "ci",
        socket=str(tmp_path / "none.sock"),
        max_concurrency=1 if bound == "application" else None,
    )

    @app.task(max_concurrency=1 if bound == "task" else None)
    async def nothing() -> None:
        pass

    async def run_twice() -> list[BaseException | None]:
        return await asyncio.gather(app.run("nothing"), app.run("nothing"), return_exceptions=True)

    # The runs of each loop wait for one another, as `run_sync` does at each call.
    for _ in range(2):
        outcomes = asyncio.run(run_twice())
        assert [type(outcome) for outcome in outcomes] == [DaemonUnavailableError] * 2
