"""Declaring and running tasks."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from fastsandbox import (
    Context,
    FastSandbox,
    Network,
    TaskError,
)
from fastsandbox.models import (
    ExecOutput,
)
from fastsandbox.testing import FakeDaemon


class Report(BaseModel):
    passed: bool
    summary: str


async def test_a_task_runs_in_a_throw_away_sandbox(
    daemon: FakeDaemon, make_app: Callable[..., FastSandbox]
) -> None:
    app = make_app()
    daemon.on_exec(lambda sandbox, cmd: ExecOutput(exit_code=0, stdout="3 passed\n"))
    seen: dict[str, Any] = {}

    @app.task(network=Network.allow("pypi.org") | Network.deny("example.org"), env={"CI": "1"})
    async def run_tests(ctx: Context, target: str, verbose: bool = False) -> Report:
        """Runs the test suite."""
        seen["sandbox"] = ctx.sandbox.name
        seen["running"] = (await ctx.sandbox.inspect()).is_running
        output = await ctx.sandbox.exec(f"make {target}")
        return Report(passed=output.ok, summary=output.stdout.strip())

    result = await app.run("run_tests", target="test")
    assert result == Report(passed=True, summary="3 passed")
    assert seen["running"]
    assert seen["sandbox"].startswith("ci-run-tests-")
    assert daemon.sandboxes == {}
    create = daemon.requests_to("POST", "/sandbox")[0].json()
    assert create["environment"] == {"CI": "1"}
    assert {(r["resources"][0], r["sandbox_id"]) for r in daemon.rules} == {
        ("pypi.org", seen["sandbox"]),
        ("example.org", seen["sandbox"]),
    }
    assert run_tests.description == "Runs the test suite."
    assert set(run_tests.input_schema["properties"]) == {"target", "verbose"}


async def test_inputs_and_results_are_validated(
    daemon: FakeDaemon, make_app: Callable[..., FastSandbox]
) -> None:
    app = make_app()

    @app.task
    async def count(times: int) -> int:
        return times * 2

    @app.task
    async def lies() -> int:
        return "not a number"  # type: ignore[return-value]

    assert await app.run("count", times="21") == 42
    with pytest.raises(ValidationError):
        await app.run("count", times="many")
    with pytest.raises(ValidationError):
        await app.run("count", times=1, extra=True)
    with pytest.raises(ValidationError):
        await app.run("lies")
    assert daemon.sandboxes == {}


async def test_keep_leaves_the_sandbox(
    daemon: FakeDaemon, make_app: Callable[..., FastSandbox]
) -> None:
    app = make_app()

    @app.task(keep=True)
    async def debug(ctx: Context) -> str:
        return ctx.sandbox.name

    name = await app.run("debug")
    assert name in daemon.sandboxes


async def test_declaration_errors(daemon: FakeDaemon, make_app: Callable[..., FastSandbox]) -> None:
    app = make_app()

    @app.task
    async def once() -> None:
        return None

    with pytest.raises(TaskError, match="already declared"):
        app.task(name="once")(lambda: None)
    with pytest.raises(TaskError, match="unknown task"):
        await app.run("missing")
    with pytest.raises(TaskError, match="unknown agent"):
        app.agent("nobody")

    @app.task
    async def no_agent(ctx: Context) -> None:
        ctx.agent  # noqa: B018

    with pytest.raises(TaskError, match="no agent"):
        await app.run("no_agent")
