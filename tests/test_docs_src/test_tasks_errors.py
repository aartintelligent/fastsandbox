"""`docs_src/tasks/errors.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.models import ExecOutput
from fastsandbox.testing import FakeDaemon


async def test_errors(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_environment.on_exec(lambda sandbox, cmd: ExecOutput(exit_code=3, stderr="failed\n"))
    await load_example("tasks/errors.py").main()
    assert capsys.readouterr().out == ("invalid inputs: 1 error\nthe script exited with code 3\n")
    assert fake_environment.sandboxes == {}
