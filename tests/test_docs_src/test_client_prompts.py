"""`docs_src/client/prompts.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon, Request, Response


async def test_prompts(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    @fake_environment.route("GET", "/user-prompts")
    def prompts(request: Request) -> Response:
        return Response(200, lines=[{"id": "prompt-1", "action": "raised"}, {"action": "synced"}])

    await load_example("client/prompts.py").main()
    assert capsys.readouterr().out == "1 prompts pending\n"
