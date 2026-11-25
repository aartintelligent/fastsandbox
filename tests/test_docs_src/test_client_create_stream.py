"""`docs_src/client/create_stream.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon


async def test_create_stream(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    await load_example("client/create_stream.py").main()
    assert capsys.readouterr().out == (
        "progress: ✓ fake kit image ready\ncreated docs-stream: running\n"
    )
    request = fake_environment.requests_to("POST", "/sandbox")[0].json()
    assert request["environment"] == {"MODE": "docs"}
    assert fake_environment.sandboxes == {}
