"""`docs_src/client/sandbox_basics.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon


async def test_sandbox_basics(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    await load_example("client/sandbox_basics.py").main()
    assert capsys.readouterr().out == "uname -sm\nhello from the host\n"
    assert fake_environment.rules[0]["resources"] == ["example.org"]
    assert fake_environment.sandboxes == {}
