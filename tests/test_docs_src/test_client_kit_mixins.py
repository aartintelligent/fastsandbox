"""`docs_src/client/kit_mixins.py`."""

from __future__ import annotations

import re
from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon


async def test_kit_mixins(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Without a kit cache on disk, the composition is forged against the fake.
    monkeypatch.delenv("FASTSANDBOX_KIT_CACHE")
    await load_example("client/kit_mixins.py").main()
    out = capsys.readouterr().out
    assert re.fullmatch(
        r"shell\+acme-tools: /kits/acme-tools\n"
        # The fake daemon echoes the last argument of a command.
        r"fastsandbox-[0-9a-f]{8}: cat ~/\.acme/config\.yaml\n",
        out,
    )
    assert fake_environment.sandboxes == {}
