"""`docs_src/agents/review_stream.py`: its declaration; running the agent needs
the real daemon and a key."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

from fastsandbox import WorkspaceDir


def test_review_is_an_agent_task(load_example: Callable[[str], ModuleType]) -> None:
    task = load_example("agents/review_stream.py").app.get_task("review")
    assert task.agent is not None
    assert task.agent.name == "claude"
    assert task.agent.output == "jsonl"
    assert task.input_schema["required"] == ["repo"]
    assert [p.marker for p in task.parameters if p.name == "repo"] == [WorkspaceDir()]
    assert task.timeout == 1800
