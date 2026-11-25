"""`docs_src/client/create.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon


async def test_create(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    await load_example("client/create.py").main()
    assert capsys.readouterr().out == (
        "docs-kept created: running\n"
        "sandboxes: docs-kept, docs-scratch\n"
        "docs-scratch after the block: None\n"
    )
    kept = fake_environment.requests_to("POST", "/sandbox")[0].json()
    assert kept["environment"] == {"MODE": "docs"}
    assert kept["cpus"] == 2
    assert fake_environment.sandboxes == {}
