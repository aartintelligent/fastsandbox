"""`docs_src/client/kits.py`."""

from __future__ import annotations

import re
from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon


async def test_kits(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The kit cache of the fake environment holds a `shell` package already.
    await load_example("client/kits.py").main()
    out = capsys.readouterr().out
    assert re.fullmatch(
        r"docker\.io/sbx/shell:latest, compiled with sbx v0\.54\.1\n"
        r"fastsandbox-[0-9a-f]{8}: agent shell\n",
        out,
    )
    assert fake_environment.sandboxes == {}
