"""`docs_src/agents/agent_command.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon


async def test_agent_command(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-anthropic-key")
    app = load_example("agents/agent_command.py").app
    command = await app.run("show_command", prompt="Explain this project")
    # The program and the run options come from the kit package.
    assert command == [
        "claude",
        "--yolo",
        "-p",
        "Explain this project",
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    pushed = fake_environment.requests_to("POST", "/sandbox/{name}/credentials")[-1].json()
    assert pushed["credential_values"] == [{"service": "anthropic", "value": "dummy-anthropic-key"}]
    allowed = {rule["resources"][0] for rule in fake_environment.rules}
    assert allowed == {"api.anthropic.com", "statsig.anthropic.com", "pypi.org"}
    assert fake_environment.sandboxes == {}
