"""`docs_src/client/mcp.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon, Request, Response


async def test_mcp(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    loaded: list[str] = []

    @fake_environment.route("GET", "/mcp/gateway-mode")
    def mode(request: Request) -> Response:
        return Response(200, {"decision": "local", "gateway_url": "none"})

    @fake_environment.route("POST", "/mcp/registration/check")
    def check(request: Request) -> Response:
        return Response(200, {"allowed": True, "name": request.json()["spec"]["Name"]})

    @fake_environment.route("POST", "/sandbox/{name}/mcp/gateway/servers")
    def load(request: Request) -> Response:
        loaded.append(request.json()["server"])
        return Response(200, {"sandbox": request.params["name"], "server": loaded[-1]})

    @fake_environment.route("GET", "/sandbox/{name}/mcp/gateway")
    def gateway(request: Request) -> Response:
        url = "http://mcp-gateway.docker.internal/mcp"
        return Response(200, {"state": "ready", "url": url, "servers": loaded})

    @fake_environment.route("DELETE", "/sandbox/{name}/mcp/gateway/servers/{server}")
    def unload(request: Request) -> Response:
        loaded.remove(request.params["server"])
        return Response(200, {"message": "unloaded"})

    await load_example("client/mcp.py").main()
    assert capsys.readouterr().out == (
        "gateway: local\n"
        "docs-tools may be registered: True\n"
        "http://mcp-gateway.docker.internal/mcp serves ['docs-tools']\n"
    )
    assert loaded == []
    assert fake_environment.sandboxes == {}
