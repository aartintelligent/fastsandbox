"""`docs_src/agents/several_agents.py`: two agent tasks on the same inputs;
running the agents needs the real daemon and their keys."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

from fastsandbox import WorkspaceDir


def test_one_task_per_agent(load_example: Callable[[str], ModuleType]) -> None:
    app = load_example("agents/several_agents.py").app
    agents = {name: task.agent.name for name, task in app.tasks.items() if task.agent}
    assert agents == {"fix_with_claude": "claude", "fix_with_codex": "codex"}
    for task in app.tasks.values():
        assert [p.marker for p in task.parameters if p.name == "repo"] == [WorkspaceDir(clone=True)]
        assert task.input_schema["required"] == ["repo", "issue"]
        assert set(task.output_schema["properties"]) == {"agent", "passed", "patch"}
