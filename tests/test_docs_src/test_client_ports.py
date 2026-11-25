"""`docs_src/client/ports.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon, Request, Response


async def test_ports(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    @fake_environment.route("POST", "/sandbox/{name}/ports")
    def publish(request: Request) -> Response:
        return Response(200, request.json())

    @fake_environment.route("POST", "/sandbox/{name}/ports/unpublish")
    def unpublish(request: Request) -> Response:
        return Response(200, {"message": "ports unpublished"})

    await load_example("client/ports.py").main()
    assert capsys.readouterr().out == "127.0.0.1:48000 -> 8000\npublished: [49000]\n"
    created = fake_environment.requests_to("POST", "/sandbox")[0].json()
    assert created["ports"] == [{"sandbox_port": 8000, "host_port": 48000, "protocol": "tcp"}]
    unpublished = fake_environment.requests_to("POST", "/sandbox/{name}/ports/unpublish")
    assert unpublished[0].json()[0]["host_port"] == 49000
    assert fake_environment.sandboxes == {}
