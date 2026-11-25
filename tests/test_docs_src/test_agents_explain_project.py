"""`docs_src/agents/explain_project.py`, the agent of the quickstart: its
declaration; running the agent needs the real daemon and a key."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

from fastsandbox import WorkspaceDir


def test_explain_works_on_a_clone(load_example: Callable[[str], ModuleType]) -> None:
    task = load_example("agents/explain_project.py").app.get_task("explain")
    assert task.agent is not None
    assert task.agent.name == "claude"
    assert [p.marker for p in task.parameters if p.name == "repo"] == [WorkspaceDir(clone=True)]
    assert task.input_schema["required"] == ["repo"]
    assert task.timeout == 900
