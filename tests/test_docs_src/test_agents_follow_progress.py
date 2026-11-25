"""`docs_src/agents/follow_progress.py`: its declaration and the progress
handler; running the agent needs the real daemon and a key."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox import WorkspaceDir


def test_review_reports_progress(
    load_example: Callable[[str], ModuleType], capsys: pytest.CaptureFixture[str]
) -> None:
    module = load_example("agents/follow_progress.py")
    task = module.app.get_task("review")
    assert task.agent is not None
    assert task.agent.output == "jsonl"
    assert [p.marker for p in task.parameters if p.name == "repo"] == [WorkspaceDir(clone=True)]
    module.show(3, None, "the agent took a step")
    assert capsys.readouterr().out == "step 3: the agent took a step\n"
