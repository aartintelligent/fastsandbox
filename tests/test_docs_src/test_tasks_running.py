"""`docs_src/tasks/running.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon


async def test_running(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    await load_example("tasks/running.py").main()
    assert capsys.readouterr().out == (
        "1/2: sandbox ready\n2/2: digest computed\nhello\n['a', 'b', 'c']\n"
    )
    assert len(fake_environment.requests_to("POST", "/sandbox")) == 4
    assert fake_environment.sandboxes == {}
