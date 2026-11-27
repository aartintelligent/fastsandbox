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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Without a kit cache on disk, the `shell` kit is forged against the fake.
    monkeypatch.delenv("FASTSANDBOX_KIT_CACHE")
    await load_example("client/kits.py").main()
    out = capsys.readouterr().out
    assert re.fullmatch(
        r"docker\.io/sbx/shell@sha256:[0-9a-f]{64}, forged for the API 0\.52\.0\n"
        r"fastsandbox-[0-9a-f]{8}: agent shell\n",
        out,
    )
    assert fake_environment.sandboxes == {}
