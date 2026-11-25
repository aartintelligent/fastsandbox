"""`docs_src/client/commands.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.models import ExecOutput
from fastsandbox.testing import FakeDaemon


async def test_commands(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    @fake_environment.on_exec
    def answer(sandbox: str, cmd: list[str]) -> ExecOutput:
        if cmd[-1] == "exit 3":
            return ExecOutput(exit_code=3, stderr="failing\n")
        return ExecOutput(exit_code=0, stdout=f"{cmd[-1]}\n")

    await load_example("client/commands.py").main()
    assert capsys.readouterr().out == (
        "exit code 0: echo hello from $(hostname)\n"
        "ok: False, exit code 3\n"
        "checked: exit code 3, stderr 'failing\\n'\n"
    )
    bodies = [r.json() for r in fake_environment.requests_to("POST", "/sandbox/{name}/exec")]
    assert bodies[0]["cmd"] == ["sh", "-c", "echo hello from $(hostname)"]
    assert bodies[1]["cmd"] == ["ls", "-la", "/tmp"]
    make = bodies[2]
    assert (make["cmd"], make["user"], make["working_dir"], make["env"]) == (
        ["make", "test"],
        "0",
        "/work",
        {"CI": "1"},
    )
    assert fake_environment.sandboxes == {}
