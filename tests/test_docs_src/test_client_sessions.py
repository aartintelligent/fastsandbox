"""`docs_src/client/sessions.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon


async def test_sessions(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    await load_example("client/sessions.py").main()
    assert capsys.readouterr().out == (
        "stopped: stopped\nin the block: running\nsession held on docs-sessions: True\n"
    )
    assert len(fake_environment.requests_to("GET", "/sandbox/{name}/session")) == 2
    assert len(fake_environment.requests_to("POST", "/sandbox/{name}/start")) == 2
    assert fake_environment.sandboxes == {}
