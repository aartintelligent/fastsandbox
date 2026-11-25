"""Tests of the agent tasks, without a daemon.

An agent run needs the real daemon and a key, so these tests check what the
task declares: its agent, its network rules, how it gets the repository, its
inputs and its result.
"""

from agents import NEEDS, Fix, app

from fastsandbox import WorkspaceDir


def test_fix_runs_claude_code() -> None:
    task = app.get_task("fix")
    assert task.agent is not None
    assert task.agent.name == "claude"
    assert task.timeout == 1800


def test_fix_works_on_a_private_clone() -> None:
    task = app.get_task("fix")
    markers = [parameter.marker for parameter in task.parameters if parameter.name == "repo"]
    assert markers == [WorkspaceDir(clone=True)]


def test_fix_reaches_the_package_index_only() -> None:
    task = app.get_task("fix")
    assert task.network == NEEDS
    assert task.allow_agent_hosts


def test_fix_inputs_and_result() -> None:
    task = app.get_task("fix")
    assert task.input_schema["required"] == ["repo", "issue"]
    assert task.output_schema == Fix.model_json_schema()
