"""The examples of `docs_src/` that need the real daemon: interactive sessions
and live events upgrade their connection, which the fake daemon does not."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest


async def test_interactive(
    load_example: Callable[[str], ModuleType], capsys: pytest.CaptureFixture[str]
) -> None:
    await load_example("client/interactive.py").main()
    assert capsys.readouterr().out == "PIPED THROUGH THE SANDBOX\nhello sandbox\n"


async def test_events(
    load_example: Callable[[str], ModuleType], capsys: pytest.CaptureFixture[str]
) -> None:
    await load_example("client/events.py").main()
    assert capsys.readouterr().out.strip()
