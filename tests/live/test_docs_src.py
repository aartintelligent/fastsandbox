"""The examples of `docs_src/` that need the real daemon: interactive sessions
and live events upgrade their connection, which the fake daemon does not, and
the install commands of a mixin run in the sandbox only."""

from __future__ import annotations

import re
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


async def test_kit_mixins(
    load_example: Callable[[str], ModuleType], capsys: pytest.CaptureFixture[str]
) -> None:
    await load_example("client/kit_mixins.py").main()
    assert re.fullmatch(
        r"shell\+acme-tools: /kits/acme-tools\n"
        r"fastsandbox-[0-9a-f]{8}: endpoint: https://api\.acme\.example\n",
        capsys.readouterr().out,
    )
