"""`docs_src/agents/network_audit.py`: its declaration and its rules; running
the agent needs the real daemon and a key."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

from fastsandbox import Network


def test_upgrade_has_its_rules(load_example: Callable[[str], ModuleType]) -> None:
    module = load_example("agents/network_audit.py")
    task = module.app.get_task("upgrade")
    assert task.agent is not None
    assert task.agent.name == "claude"
    assert task.allow_agent_hosts
    assert task.network == module.NEEDS | Network.deny("example.org")
    assert [change.action for change in task.network.changes] == ["allow", "http-allow", "deny"]
    assert task.input_schema["required"] == ["repo", "package"]
    assert set(task.output_schema["properties"]) == {"ok", "reached", "refused"}
