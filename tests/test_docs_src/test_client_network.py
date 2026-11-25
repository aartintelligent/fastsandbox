"""`docs_src/client/network.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon, Request, Response


async def test_network(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    @fake_environment.route("POST", "/policy/network/check")
    def check(request: Request) -> Response:
        return Response(200, {"allowed": True, "target": request.json()["target"]})

    @fake_environment.route("GET", "/policy/network/log")
    def log(request: Request) -> Response:
        blocked = [
            {"host": "example.org:443", "vm_name": "docs-network", "count_since": 2},
            {"host": "example.org:443", "vm_name": "another-sandbox", "count_since": 1},
        ]
        return Response(200, {"allowed_hosts": [], "blocked_hosts": blocked})

    await load_example("client/network.py").main()
    assert capsys.readouterr().out == (
        "applied: True\n"
        "allow pypi.org\n"
        "allow files.pythonhosted.org\n"
        "deny example.org\n"
        "deny api.example.com\n"
        "api.anthropic.com allowed: True\n"
        "blocked: example.org:443 (2 times)\n"
    )
    http = fake_environment.requests_to("POST", "/policy/network/rules")[-1].json()["actions"][0]
    assert http["methods"] == ["POST"]
    assert http["path"] == "/admin/**"
    assert http["sandbox_id"] == "docs-network"
    assert fake_environment.sandboxes == {}
