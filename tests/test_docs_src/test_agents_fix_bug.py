"""`docs_src/agents/fix_bug.py`: its declaration; running the agent needs the
real daemon and a key."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType


def test_fix_bug_is_an_agent_task(load_example: Callable[[str], ModuleType]) -> None:
    task = load_example("agents/fix_bug.py").app.get_task("fix_bug")
    assert task.agent is not None
    assert task.agent.name == "claude"
    assert set(task.input_schema["properties"]) == {"repo", "issue", "command"}
    assert task.input_schema["required"] == ["repo", "issue"]
    assert task.timeout == 1200
