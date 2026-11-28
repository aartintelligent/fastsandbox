"""Tasks that run a coding agent."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from fastsandbox import (
    AgentRunner,
    FastSandbox,
    KitPackage,
    Network,
)
from fastsandbox.testing import FakeDaemon, Request, Response


async def test_agent_tasks(
    daemon: FakeDaemon,
    claude_package: KitPackage,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-anthropic-key")
    app = FastSandbox("ci", socket=str(daemon.socket_path))

    @app.agent("claude", kit=None, network=Network.deny("example.org"))
    async def fix(agent: AgentRunner, issue: str) -> list[str]:
        assert agent.name == "claude"
        return agent.command(f"Fix: {issue}")

    fix.kit = claude_package
    command = await app.run("fix", issue="the build")
    assert command[:3] == ["claude", "--yolo", "-p"]
    assert command[3] == "Fix: the build"
    # The first push, empty, is the one every creation makes, as `sbx` does.
    credentials = daemon.requests_to("POST", "/sandbox/{name}/credentials")[-1].json()
    assert credentials["credential_values"] == [
        {"service": "anthropic", "value": "dummy-anthropic-key"}
    ]
    allowed = {r["resources"][0] for r in daemon.rules if r["decision"] == "allow"}
    assert allowed == {"api.anthropic.com", "statsig.anthropic.com"}
    # The daemon withholds nothing: nothing is reported.
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


def agent_app(daemon: FakeDaemon, package: KitPackage) -> FastSandbox:
    """An application whose task `fix` runs the agent of `package` and returns its name."""
    app = FastSandbox("ci", socket=str(daemon.socket_path))

    @app.agent("claude", kit=None)
    async def fix(agent: AgentRunner) -> str:
        return agent.name

    fix.kit = package
    return app


def warnings_of(caplog: pytest.LogCaptureFixture, task: str) -> list[str]:
    """The warnings logged for the task `task`."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == f"fastsandbox.task.{task}" and record.levelno == logging.WARNING
    ]


async def test_a_credential_withheld_when_pushed_is_reported(
    daemon: FakeDaemon,
    claude_package: KitPackage,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-anthropic-key")

    @daemon.route("POST", "/sandbox/{name}/credentials")
    def withheld(request: Request) -> Response:
        return Response(200, {"message": "Credentials updated", "withheld": ["anthropic"]})

    assert await agent_app(daemon, claude_package).run("fix") == "claude"
    [warning] = warnings_of(caplog, "fix")
    assert "the daemon withholds the credentials anthropic" in warning
    assert "pushed from the environment for anthropic" in warning
    assert "dummy-anthropic-key" not in warning


async def test_a_credential_withheld_at_creation_is_reported(
    daemon: FakeDaemon,
    claude_package: KitPackage,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    @daemon.route("POST", "/sandbox")
    def create(request: Request) -> Response:
        body = request.json()
        created: dict[str, Any] = {
            "id": "sandbox-1",
            "name": body["name"],
            "agent": body["agent"],
            "status": "running",
            "workspace": "",
        }
        daemon.sandboxes[body["name"]] = {**created, "ports": [], "labels": {}, "request": body}
        return Response(200, lines=[{"result": {**created, "withheld": ["anthropic"]}}])

    assert await agent_app(daemon, claude_package).run("fix") == "claude"
    [warning] = warnings_of(caplog, "fix")
    assert "the daemon withholds the credentials anthropic" in warning
    assert "pushed from the environment" not in warning
