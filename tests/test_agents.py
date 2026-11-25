"""Tasks that run a coding agent."""

from __future__ import annotations

import pytest

from fastsandbox import (
    AgentRunner,
    FastSandbox,
    KitPackage,
    Network,
)
from fastsandbox.testing import FakeDaemon


async def test_agent_tasks(
    daemon: FakeDaemon, claude_package: KitPackage, monkeypatch: pytest.MonkeyPatch
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
