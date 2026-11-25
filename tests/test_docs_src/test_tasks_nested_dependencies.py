"""`docs_src/tasks/nested_dependencies.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

from fastsandbox.models import ExecOutput
from fastsandbox.testing import FakeDaemon


def answer(sandbox: str, cmd: list[str]) -> ExecOutput:
    outputs = {"mktemp": "/tmp/tmp.x1\n", "wc": "3 /tmp/tmp.x1/input.txt\n"}
    return ExecOutput(exit_code=0, stdout=outputs.get(cmd[0], ""))


async def test_nested_dependencies(
    fake_environment: FakeDaemon, load_example: Callable[[str], ModuleType]
) -> None:
    fake_environment.on_exec(answer)
    app = load_example("tasks/nested_dependencies.py").app
    assert await app.run("count_lines") == {"lines": "3", "scratch": "/tmp/tmp.x1"}
    commands = [
        r.json()["cmd"] for r in fake_environment.requests_to("POST", "/sandbox/{name}/exec")
    ]
    # One scratch directory for the run, shared by both dependents, removed last.
    assert [c for c in commands if c[0] == "mktemp"] == [["mktemp", "-d"]]
    assert commands[-1] == ["rm", "-rf", "/tmp/tmp.x1"]
    upload = fake_environment.requests_to("PUT", "/sandbox/{name}/files")[0]
    assert upload.query["path"] == "/tmp/tmp.x1"
