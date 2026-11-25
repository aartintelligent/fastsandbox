"""`docs_src/agents/mcp_tools.py`: its declaration; loading a server and
running the agent need the real daemon, a registered server and a key."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

from fastsandbox import WorkspaceDir


def test_check_docs_is_an_agent_task(load_example: Callable[[str], ModuleType]) -> None:
    task = load_example("agents/mcp_tools.py").app.get_task("check_docs")
    assert task.agent is not None
    assert task.agent.name == "claude"
    assert [p.marker for p in task.parameters if p.name == "repo"] == [WorkspaceDir(clone=True)]
    assert task.timeout == 1200
