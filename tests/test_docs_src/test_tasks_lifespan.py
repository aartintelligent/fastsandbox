"""`docs_src/tasks/lifespan.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon


async def test_lifespan(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    await load_example("tasks/lifespan.py").main()
    assert capsys.readouterr().out == "one\ntwo\nthree\ndigests: 3 runs\n"
    # One client for the three runs: one health check.
    assert len(fake_environment.requests_to("GET", "/daemon/health")) == 1
    assert fake_environment.sandboxes == {}
