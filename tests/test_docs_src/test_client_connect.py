"""`docs_src/client/connect.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

import fastsandbox
from fastsandbox.testing import FakeDaemon


async def test_connect(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    await load_example("client/connect.py").main()
    low, high = fastsandbox.SUPPORTED_API
    assert capsys.readouterr().out == (
        "sbx v0.54.1, API 0.52.0, healthy\n"
        f"supported API: from {low} up to {high}, excluded\n"
        "0 sandboxes\n"
    )
