"""`docs_src/client/daemon.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon, Request, Response


async def test_daemon(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    @fake_environment.route("GET", "/daemon/settings")
    def settings(request: Request) -> Response:
        return Response(
            200,
            {
                "settings": [
                    {"key": "a.default", "value": 1, "default": 1, "source": "default"},
                    {"key": "b.changed", "value": True, "default": False, "source": "override"},
                ]
            },
        )

    @fake_environment.route("GET", "/daemon/loglevel")
    def levels(request: Request) -> Response:
        return Response(200, {"general": "info", "proxy": "debug"})

    @fake_environment.route("GET", "/daemon/disk-usage")
    def disk(request: Request) -> Response:
        summary = {"type": "Images", "total_count": 3, "size": 2048, "reclaimable": 1024}
        return Response(200, {"summaries": [summary]})

    await load_example("client/daemon.py").main()
    assert capsys.readouterr().out == (
        "sbx v0.54.1: healthy True\n"
        "b.changed = True (override)\n"
        "log level of general: info\n"
        "log level of proxy: debug\n"
        "Images: 2048 bytes, 1024 reclaimable\n"
    )
