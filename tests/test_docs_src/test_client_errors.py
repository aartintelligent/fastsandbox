"""`docs_src/client/errors.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon


async def test_errors(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    await load_example("client/errors.py").main()
    assert capsys.readouterr().out == (
        "not found: HTTP 404, during sandbox inspection\nconflict: HTTP 409, transient True\n"
    )
    assert fake_environment.sandboxes == {}
